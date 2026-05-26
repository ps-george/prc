from __future__ import annotations

from prc.phases.verdict import synthesize
from prc.verdict import (
    AuthorResponse,
    Category,
    Issue,
    Location,
    Severity,
    is_substantive,
)


def _issue(severity: Severity, ident: str = "x") -> Issue:
    return Issue(
        id=ident,
        severity=severity,
        category=Category.CORRECTNESS,
        location=Location(file="a.py", line=1),
        title="t",
        detail="d",
    )


def test_synthesize_blocker_requests_changes() -> None:
    v = synthesize("s", [_issue(Severity.BLOCKER)])
    assert v.decision == "request_changes"


def test_synthesize_major_only_discusses() -> None:
    v = synthesize("s", [_issue(Severity.MAJOR)])
    assert v.decision == "discuss"


def test_synthesize_minor_only_approves() -> None:
    v = synthesize("s", [_issue(Severity.MINOR)])
    assert v.decision == "approve"


def test_synthesize_no_issues_approves() -> None:
    v = synthesize("s", [])
    assert v.decision == "approve"


def test_substantive_rejects_single_word() -> None:
    r = AuthorResponse(issue_id="1", action="refute", note="no")
    assert not is_substantive(r)


def test_substantive_accepts_real_response() -> None:
    r = AuthorResponse(
        issue_id="1", action="accept", note="will fix in the next commit"
    )
    assert is_substantive(r)
