"""Phase 1 — Understand. Produce a short structured summary of the change."""

from __future__ import annotations

from prc.diff import Diff
from prc.llm import LLMClient

SYSTEM = (
    "You are a careful code reviewer. Read the diff and produce a tight "
    "summary of WHAT changes, WHY (as best you can infer), and WHAT it "
    "touches. Three short paragraphs, no preamble."
)


def _render_diff(diff: Diff, max_chars: int = 30_000) -> str:
    parts = [f"Commit subject: {diff.subject}"]
    if diff.body:
        parts.append(f"Commit body:\n{diff.body}")
    for f in diff.files:
        parts.append(f"--- {f.path} ---\n{f.patch}")
    text = "\n\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n…[truncated]"
    return text


async def run(diff: Diff, llm: LLMClient) -> str:
    user = _render_diff(diff)
    resp = await llm.complete(SYSTEM, [{"role": "user", "content": user}])
    return resp.content.strip()
