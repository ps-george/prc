"""End-to-end review pipeline. v0.1.0 runs the ``quick`` mode only."""

from __future__ import annotations

from prc.diff import Diff
from prc.llm import LLMClient
from prc.phases import correctness, understand, verdict
from prc.verdict import Verdict


async def review_quick(diff: Diff, llm: LLMClient) -> Verdict:
    """Sequential ``understand → correctness → verdict`` pipeline."""
    summary = await understand.run(diff, llm)
    issues = await correctness.run(diff, summary, llm)
    return verdict.synthesize(summary, issues)
