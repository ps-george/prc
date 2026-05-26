"""Bench-A — synthetic injected-bug benchmark.

Scaffolding only in v0.1.0. The runner loads the hand-curated fixtures
in ``benchmarks/fixtures/`` and, for each one, asks the configured
review pipeline whether the injected bug was flagged as a blocker or
major issue.

Each fixture is a JSON document with:

::

    {
      "id": "off-by-one-01",
      "bug_type": "off_by_one",
      "summary": "human description of the injected bug",
      "diff": "<unified diff text>",
      "bug_location": {"file": "x.py", "line": 12}
    }

A fixture is considered *caught* when the resulting verdict contains
at least one blocker- or major-severity issue whose ``location.file``
matches the bug location's file. Line-level matching is too brittle to
gate on at this size.

Run with::

    PRC_MOCK=1 uv run python -m benchmarks.bench_a

No published results are claimed yet — the runner exists so v0.2 can
measure deltas across model + prompt iterations.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from prc.diff import Diff, FileDiff
from prc.llm import LLMClient, MockLLMClient, client_from_env
from prc.pipeline import review_quick
from prc.verdict import Severity

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class Fixture:
    id: str
    bug_type: str
    summary: str
    diff: Diff
    bug_file: str

    @classmethod
    def load(cls, path: Path) -> Fixture:
        data = json.loads(path.read_text())
        diff = Diff(
            ref=data["id"],
            subject=data.get("summary", ""),
            body="",
            files=[FileDiff(path=data["bug_location"]["file"], patch=data["diff"])],
        )
        return cls(
            id=data["id"],
            bug_type=data["bug_type"],
            summary=data["summary"],
            diff=diff,
            bug_file=data["bug_location"]["file"],
        )


def load_fixtures() -> list[Fixture]:
    return sorted(
        (Fixture.load(p) for p in FIXTURE_DIR.glob("*.json")),
        key=lambda f: f.id,
    )


def _mock_llm_for(fixture: Fixture) -> LLMClient:
    """Mock LLM that always 'catches' the bug — for runner self-test."""
    mock = MockLLMClient()
    mock.queue(f"Fixture {fixture.id}: {fixture.summary}")
    issue = {
        "severity": "blocker",
        "category": "correctness",
        "file": fixture.bug_file,
        "line": None,
        "title": f"Injected {fixture.bug_type}",
        "detail": "Mock detection used by the bench self-test.",
    }
    mock.queue(json.dumps([issue]))
    return mock


async def run() -> dict[str, object]:
    fixtures = load_fixtures()
    use_mock = os.environ.get("PRC_MOCK") == "1"
    caught: list[str] = []
    missed: list[str] = []
    by_type: Counter[str] = Counter()
    by_type_caught: Counter[str] = Counter()
    for fx in fixtures:
        by_type[fx.bug_type] += 1
        llm: LLMClient = _mock_llm_for(fx) if use_mock else client_from_env()
        verdict = await review_quick(fx.diff, llm)
        flagged = any(
            i.severity in (Severity.BLOCKER, Severity.MAJOR)
            and i.location.file == fx.bug_file
            for i in verdict.issues
        )
        if flagged:
            caught.append(fx.id)
            by_type_caught[fx.bug_type] += 1
        else:
            missed.append(fx.id)
    return {
        "total": len(fixtures),
        "caught": caught,
        "missed": missed,
        "recall_overall": (len(caught) / len(fixtures)) if fixtures else 0.0,
        "recall_by_type": {
            t: (by_type_caught[t] / by_type[t]) for t in by_type
        },
    }


def main() -> None:
    result = asyncio.run(run())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
