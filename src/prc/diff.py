"""Parse a git ref (or short PR URL) into a structured diff.

v0.1.0 supports local git refs only. PR-URL handling is stubbed and
errors out cleanly — it lands in v0.2 alongside the GitHub integration.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FileDiff:
    path: str
    patch: str


@dataclass(frozen=True)
class Diff:
    """A parsed diff for a single git ref vs its parent."""

    ref: str
    subject: str
    body: str
    files: list[FileDiff] = field(default_factory=list)

    def total_changed_lines(self) -> int:
        return sum(
            1
            for f in self.files
            for line in f.patch.splitlines()
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        )


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def parse_ref(ref: str, *, repo: Path | None = None) -> Diff:
    """Parse a git ref into a structured :class:`Diff`.

    The ref is compared against ``<ref>^`` (i.e. its first parent).
    """
    if ref.startswith(("http://", "https://")):
        raise NotImplementedError(
            "PR-URL parsing is not implemented in v0.1.0. Pass a local git ref."
        )
    cwd = repo or Path.cwd()
    subject = _run_git(["log", "-1", "--pretty=%s", ref], cwd).strip()
    body = _run_git(["log", "-1", "--pretty=%b", ref], cwd).strip()
    name_status = _run_git(
        ["diff", "--name-only", f"{ref}^", ref], cwd
    ).strip().splitlines()
    files: list[FileDiff] = []
    for path in name_status:
        if not path:
            continue
        patch = _run_git(["diff", f"{ref}^", ref, "--", path], cwd)
        files.append(FileDiff(path=path, patch=patch))
    return Diff(ref=ref, subject=subject, body=body, files=files)
