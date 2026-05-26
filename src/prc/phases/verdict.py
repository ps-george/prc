"""Phase 3 — Verdict synthesis."""

from __future__ import annotations

from prc.verdict import Decision, Issue, Severity, Verdict


def synthesize(summary: str, issues: list[Issue]) -> Verdict:
    """Decide a top-level disposition from the phase outputs.

    Rule: any blocker => ``request_changes``; any major => ``discuss``;
    otherwise => ``approve``. Deterministic so callers can reason about
    the output without a second LLM round-trip.
    """
    if any(i.severity == Severity.BLOCKER for i in issues):
        decision: Decision = "request_changes"
    elif any(i.severity == Severity.MAJOR for i in issues):
        decision = "discuss"
    else:
        decision = "approve"
    return Verdict(decision=decision, summary=summary, issues=issues)
