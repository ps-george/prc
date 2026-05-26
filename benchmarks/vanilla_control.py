"""Vanilla-LLM control — single-call "review this PR" baseline.

The same SWE-bench instances run through ``real_bugs.py`` are fed into
a single chat-completions call with a minimal "did you find any bugs?"
prompt. The point is to measure whether prc's structured pipeline adds
real value over a one-shot review with the same model.

Scoring is intentionally lenient — we look for any blocker/critical/
major/bug-flavoured language plus the bug file's basename appearing in
the response. This biases *toward* the vanilla control (against the
hypothesis we're hoping for) so the comparison is honest.
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

from benchmarks.real_bugs import DATA_DIR, Instance, load_instances
from prc.llm import LLMClient, client_from_env

VANILLA_SYSTEM = (
    "You are an experienced software engineer doing a code review. "
    "Read the diff. If you find any real bugs (correctness issues, "
    "logic errors, missing edge cases, regressions), say so explicitly. "
    "If the change looks fine, say it looks fine. Keep it short."
)


VANILLA_USER_TEMPLATE = """\
Please review this PR. Did you find any bugs?

Subject: {subject}
Repo: {repo}

Diff:
{diff_text}
"""


_BUG_WORDS = re.compile(
    r"\b(bug|regression|incorrect|broken|breaks|wrong|"
    r"off[- ]by[- ]one|null|undefined|missing|"
    r"crash|exception|race|leak|"
    r"blocker|critical|major|severity|"
    r"problem|issue|defect|flaw|mistake|"
    r"will fail|will break|won['’]t work|fails to|"
    r"regress|reverts|reintroduce)\b",
    re.IGNORECASE,
)

# Phrases that strongly indicate the model concluded the diff is fine.
_CLEAN_PHRASES = re.compile(
    r"\b(no bugs?|no issues?|looks (?:fine|good|correct|ok|okay)|"
    r"appears (?:fine|correct|ok)|"
    r"don['’]t (?:see|find)\s+(?:any\s+)?(?:bugs?|issues?|problems?)|"
    r"do not (?:see|find)\s+(?:any\s+)?(?:bugs?|issues?|problems?)|"
    r"(?:i|i'?ve)\s+did(?:n['’]t| not)\s+find|"
    r"nothing (?:wrong|obvious))\b",
    re.IGNORECASE,
)

# Strong affirmatives — model explicitly says yes / there is a bug.
_AFFIRMATIVE = re.compile(
    r"\b(yes[,.\s]|there['’]?s a bug|there is a bug|"
    r"this is (?:a )?(?:bug|regression|incorrect|broken|wrong)|"
    r"i (?:found|see|noticed)|"
    r"the (?:bug|issue|problem|defect|regression) is|"
    r"this (?:will|would) (?:break|fail|cause|introduce))\b",
    re.IGNORECASE,
)


def _diff_text_for(inst: Instance) -> str:
    return inst.reversed_patch


def response_catches_bug(response_text: str, bug_file: str) -> bool:
    """Detect whether the vanilla response affirmatively flagged a bug.

    Two-stage: (1) strong affirmative phrase ("yes", "there's a bug",
    "this will break", "the bug is", ...) — counts as caught regardless
    of clean-phrase presence; (2) otherwise require bug-flavoured
    vocabulary AND no dominant "looks fine / no issues" clean phrase.

    File-path mention is NOT required — most vanilla replies describe
    the bug by behaviour, not by path. That made the earlier
    file-required scoring artificially zero.
    """
    text = response_text.strip()
    if not text:
        return False
    if _AFFIRMATIVE.search(text):
        # If the model also explicitly says "no bugs", treat as miss.
        not_an_explicit_clean = not (
            _CLEAN_PHRASES.search(text) and not _BUG_WORDS.search(text)
        )
        return not_an_explicit_clean
    return bool(_BUG_WORDS.search(text) and not _CLEAN_PHRASES.search(text))


@dataclass(frozen=True)
class VanillaResult:
    instance_id: str
    repo: str
    bug_file: str
    patch_lines: int
    caught: bool
    response_chars: int
    mentioned_file: bool
    mentioned_bug_words: bool
    response_text: str = ""
    error: str | None = None


async def run_vanilla_on_instance(
    inst: Instance, llm: LLMClient
) -> VanillaResult:
    user = VANILLA_USER_TEMPLATE.format(
        subject=f"Refactor in {inst.repo}",
        repo=inst.repo,
        diff_text=_diff_text_for(inst),
    )
    try:
        resp = await llm.complete(
            VANILLA_SYSTEM, [{"role": "user", "content": user}]
        )
    except Exception as exc:  # noqa: BLE001 -- bench must keep going
        return VanillaResult(
            instance_id=inst.instance_id,
            repo=inst.repo,
            bug_file=inst.bug_file,
            patch_lines=inst.patch_lines,
            caught=False,
            response_chars=0,
            mentioned_file=False,
            mentioned_bug_words=False,
            error=f"{type(exc).__name__}: {exc}",
        )
    text = resp.content
    caught = response_catches_bug(text, inst.bug_file)
    basename = Path(inst.bug_file).name
    return VanillaResult(
        instance_id=inst.instance_id,
        repo=inst.repo,
        bug_file=inst.bug_file,
        patch_lines=inst.patch_lines,
        caught=caught,
        response_chars=len(text),
        mentioned_file=bool(basename and basename in text),
        mentioned_bug_words=bool(_BUG_WORDS.search(text)),
        response_text=text,
    )


async def run_all(
    instances: Iterable[Instance], llm_factory: Callable[[], LLMClient]
) -> list[VanillaResult]:
    results: list[VanillaResult] = []
    for inst in instances:
        llm = llm_factory()
        result = await run_vanilla_on_instance(inst, llm)
        results.append(result)
        print(
            f"[vanilla] {result.instance_id:50s} "
            f"caught={result.caught} chars={result.response_chars}"
            f"{' ERR=' + result.error if result.error else ''}",
            flush=True,
        )
    return results


def summarise(results: list[VanillaResult]) -> dict[str, Any]:
    n = len(results)
    caught = sum(1 for r in results if r.caught)
    errors = sum(1 for r in results if r.error)
    return {
        "n": n,
        "caught": caught,
        "missed": n - caught - errors,
        "errors": errors,
        "recall": (caught / n) if n else 0.0,
        "per_instance": [r.__dict__ for r in results],
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
