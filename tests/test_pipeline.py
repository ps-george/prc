from __future__ import annotations

from prc.diff import Diff, FileDiff
from prc.llm import MockLLMClient
from prc.output import markdown
from prc.pipeline import review_quick


def _toy_diff() -> Diff:
    return Diff(
        ref="HEAD",
        subject="add helper",
        body="",
        files=[FileDiff(path="x.py", patch="+def f():\n+    return 1\n")],
    )


async def test_review_quick_end_to_end() -> None:
    mock = MockLLMClient()
    mock.queue("Adds a tiny helper. No tests added.")
    mock.queue(
        '[{"severity":"blocker","category":"correctness","file":"x.py",'
        '"line":2,"title":"Always returns 1",'
        '"detail":"The helper ignores its inputs."}]'
    )
    verdict = await review_quick(_toy_diff(), mock)
    assert verdict.decision == "request_changes"
    assert len(verdict.issues) == 1
    assert verdict.issues[0].title == "Always returns 1"
    out = markdown.render(verdict, ref="HEAD")
    assert "REQUEST CHANGES" in out
    assert "Always returns 1" in out


async def test_review_quick_clean_diff_approves() -> None:
    mock = MockLLMClient()
    mock.queue("Trivial doc tweak.")
    mock.queue("[]")
    verdict = await review_quick(_toy_diff(), mock)
    assert verdict.decision == "approve"
    assert verdict.issues == []


async def test_review_quick_handles_garbage_llm_output() -> None:
    mock = MockLLMClient()
    mock.queue("ok.")
    mock.queue("not json at all")
    verdict = await review_quick(_toy_diff(), mock)
    assert verdict.decision == "approve"
