"""Render a :class:`Verdict` as structured markdown."""

from __future__ import annotations

from prc.verdict import Severity, Verdict

_DECISION_LABEL = {
    "approve": "APPROVE",
    "request_changes": "REQUEST CHANGES",
    "discuss": "DISCUSS",
}

_SEVERITY_ORDER = [Severity.BLOCKER, Severity.MAJOR, Severity.MINOR]


def render(verdict: Verdict, *, ref: str | None = None) -> str:
    lines: list[str] = []
    header = f"# PR Review — {_DECISION_LABEL[verdict.decision]}"
    if ref:
        header += f" ({ref})"
    lines.append(header)
    lines.append("")
    lines.append("## Summary")
    lines.append(verdict.summary or "_(no summary)_")
    lines.append("")
    lines.append("## Issues")
    if not verdict.issues:
        lines.append("_None found._")
        lines.append("")
    else:
        for severity in _SEVERITY_ORDER:
            bucket = [i for i in verdict.issues if i.severity == severity]
            if not bucket:
                continue
            lines.append(f"### {severity.value.title()} ({len(bucket)})")
            for issue in bucket:
                loc = issue.location.file
                if issue.location.line is not None:
                    loc += f":{issue.location.line}"
                lines.append(f"- **[{issue.id}] {issue.title}** — `{loc}` · {issue.category.value}")
                lines.append(f"  - {issue.detail}")
                if issue.suggested_fix:
                    lines.append(f"  - _Suggested fix:_ {issue.suggested_fix}")
            lines.append("")
    lines.append("## Author response")
    lines.append(
        "Each blocker and major issue expects one of: `accept` (commit to a fix), "
        "`refute` (explain why it isn't an issue), or `clarify` (ask for more "
        "detail). A response of fewer than three words is rejected as "
        "non-substantive. The review is not considered complete until every "
        "blocker and major issue has a substantive response."
    )
    return "\n".join(lines).rstrip() + "\n"
