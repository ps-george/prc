"""Real-bugs benchmark — review reversed SWE-bench Verified patches with prc.

For each instance we:
  1. Take the human-validated ``golden_patch``.
  2. Reverse it to produce a *bug-introducing* unified diff (the kind of
     change a contributor might propose that would *undo* a real fix and
     reintroduce a real bug).
  3. Hand that synthetic diff to prc's review pipeline as if it were a PR.
  4. Record whether prc flagged a blocker- or major-severity issue
     against the file the original bug lived in.

The dataset is loaded lazily from ``benchmarks/data/sample_*.json`` —
selection is owned by a separate script so this module stays a pure
adapter and has no network dependency at import time.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prc.diff import Diff, FileDiff
from prc.llm import LLMClient, client_from_env
from prc.pipeline import review_quick
from prc.verdict import Severity, Verdict

DATA_DIR = Path(__file__).parent / "data"


# --------------------------------------------------------------------------- #
# Diff reversal
# --------------------------------------------------------------------------- #


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


def reverse_unified_diff(patch: str) -> str:
    """Reverse a unified diff so applying it undoes the original change.

    Swaps ``---``/``+++`` headers, ``+``/``-`` line prefixes, and the
    ``@@`` hunk old/new line ranges. Lines that don't match any of those
    patterns (context, ``diff --git`` headers, ``index`` lines, etc.)
    are passed through unchanged.
    """
    out: list[str] = []
    for line in patch.splitlines(keepends=False):
        if line.startswith("--- "):
            out.append("+++ " + line[4:])
            continue
        if line.startswith("+++ "):
            out.append("--- " + line[4:])
            continue
        m = _HUNK_RE.match(line)
        if m:
            old_start, old_len, new_start, new_len, tail = m.groups()
            ol = old_len if old_len is not None else "1"
            nl = new_len if new_len is not None else "1"
            out.append(f"@@ -{new_start},{nl} +{old_start},{ol} @@{tail}")
            continue
        if line.startswith("+") and not line.startswith("+++"):
            out.append("-" + line[1:])
            continue
        if line.startswith("-") and not line.startswith("---"):
            out.append("+" + line[1:])
            continue
        out.append(line)
    return "\n".join(out) + ("\n" if patch.endswith("\n") else "")


# --------------------------------------------------------------------------- #
# Instance + result types
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Instance:
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    bug_file: str
    patch_lines: int
    forward_patch: str  # the original golden_patch (the fix)
    reversed_patch: str  # bug-introducing diff


def load_instances(sample_path: Path) -> list[Instance]:
    raw = json.loads(sample_path.read_text())
    out: list[Instance] = []
    for r in raw:
        out.append(
            Instance(
                instance_id=r["instance_id"],
                repo=r["repo"],
                base_commit=r["base_commit"],
                problem_statement=r["problem_statement"],
                bug_file=r["bug_file"],
                patch_lines=int(r["patch_lines"]),
                forward_patch=r["patch"],
                reversed_patch=reverse_unified_diff(r["patch"]),
            )
        )
    return out


def instance_to_diff(inst: Instance, *, direction: str = "reversed") -> Diff:
    """Build a ``Diff`` payload from an instance.

    ``direction='reversed'`` (default) hands prc the bug-introducing
    diff. ``direction='forward'`` hands prc the real human-validated
    fix — used as a false-positive control: a reviewer that flags fixes
    as bugs is just noisy.
    """
    patch = inst.reversed_patch if direction == "reversed" else inst.forward_patch
    files = _split_unified_diff_by_file(patch)
    if not files:
        files = [(inst.bug_file, patch)]
    subject = f"Refactor in {inst.repo}@{inst.base_commit[:7]}"
    if direction == "reversed":
        body = (
            "Synthetic PR generated from the reverse of a human-validated "
            "fix. Treat as a normal contributor change."
        )
    else:
        body = (
            "Synthetic PR replaying a human-validated fix. Treat as a "
            "normal contributor change."
        )
    return Diff(
        ref=inst.instance_id,
        subject=subject,
        body=body,
        files=[FileDiff(path=p, patch=t) for p, t in files],
    )


def _split_unified_diff_by_file(patch: str) -> list[tuple[str, str]]:
    """Split a multi-file unified diff into ``[(path, file_patch), ...]``."""
    lines = patch.splitlines(keepends=True)
    chunks: list[tuple[str, list[str]]] = []
    current_path: str | None = None
    current: list[str] = []
    for line in lines:
        if line.startswith("diff --git "):
            if current_path is not None:
                chunks.append((current_path, current))
            current = [line]
            current_path = None
            continue
        if line.startswith("+++ b/") and current_path is None:
            current_path = line[6:].rstrip("\n")
        if line.startswith("--- a/") and current_path is None:
            current_path = line[6:].rstrip("\n")
        current.append(line)
    if current and current_path is not None:
        chunks.append((current_path, current))
    return [(p, "".join(c)) for p, c in chunks]


# --------------------------------------------------------------------------- #
# Recall scoring
# --------------------------------------------------------------------------- #


def verdict_catches_bug(verdict: Verdict, bug_file: str) -> bool:
    """A verdict catches the bug iff it has a blocker/major issue at the file."""
    target = _norm_path(bug_file)
    for issue in verdict.issues:
        if issue.severity not in (Severity.BLOCKER, Severity.MAJOR):
            continue
        if _norm_path(issue.location.file) == target:
            return True
        # Lenient: basename match (LLMs often drop the leading repo path)
        if Path(_norm_path(issue.location.file)).name == Path(target).name:
            return True
    return False


def _norm_path(p: str) -> str:
    return p.strip().lstrip("./").replace("\\", "/")


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class InstanceResult:
    instance_id: str
    repo: str
    bug_file: str
    patch_lines: int
    caught: bool
    decision: str
    blocker_count: int
    major_count: int
    issue_titles: tuple[str, ...]
    error: str | None = None


async def run_prc_on_instance(
    inst: Instance, llm: LLMClient, *, direction: str = "reversed"
) -> InstanceResult:
    diff = instance_to_diff(inst, direction=direction)
    try:
        verdict = await review_quick(diff, llm)
    except Exception as exc:  # noqa: BLE001 — benchmark must keep going
        return InstanceResult(
            instance_id=inst.instance_id,
            repo=inst.repo,
            bug_file=inst.bug_file,
            patch_lines=inst.patch_lines,
            caught=False,
            decision="error",
            blocker_count=0,
            major_count=0,
            issue_titles=(),
            error=f"{type(exc).__name__}: {exc}",
        )
    caught = verdict_catches_bug(verdict, inst.bug_file)
    blockers = sum(1 for i in verdict.issues if i.severity == Severity.BLOCKER)
    majors = sum(1 for i in verdict.issues if i.severity == Severity.MAJOR)
    titles = tuple(
        i.title
        for i in verdict.issues
        if i.severity in (Severity.BLOCKER, Severity.MAJOR)
    )
    return InstanceResult(
        instance_id=inst.instance_id,
        repo=inst.repo,
        bug_file=inst.bug_file,
        patch_lines=inst.patch_lines,
        caught=caught,
        decision=verdict.decision,
        blocker_count=blockers,
        major_count=majors,
        issue_titles=titles,
    )


async def run_all(
    instances: Iterable[Instance],
    llm_factory: Callable[[], LLMClient],
    *,
    direction: str = "reversed",
    tag: str = "prc",
) -> list[InstanceResult]:
    results: list[InstanceResult] = []
    for inst in instances:
        llm = llm_factory()
        result = await run_prc_on_instance(inst, llm, direction=direction)
        results.append(result)
        print(
            f"[{tag}] {result.instance_id:50s} "
            f"caught={result.caught} decision={result.decision} "
            f"blockers={result.blocker_count} majors={result.major_count}"
            f"{' ERR=' + result.error if result.error else ''}",
            flush=True,
        )
    return results


def summarise(results: list[InstanceResult]) -> dict[str, Any]:
    n = len(results)
    caught = sum(1 for r in results if r.caught)
    errors = sum(1 for r in results if r.error)
    return {
        "n": n,
        "caught": caught,
        "missed": n - caught - errors,
        "errors": errors,
        "recall": (caught / n) if n else 0.0,
        "per_instance": [
            {**r.__dict__, "issue_titles": list(r.issue_titles)} for r in results
        ],
    }


def main() -> None:
    sample = DATA_DIR / "sample_20.json"
    instances = load_instances(sample)
    if os.environ.get("PRC_MODEL") is None:
        raise SystemExit("Set PRC_MODEL (and PRC_API_KEY/PRC_API_BASE) to run.")
    results = asyncio.run(run_all(instances, client_from_env))
    print(json.dumps(summarise(results), indent=2, default=str))


if __name__ == "__main__":
    main()
