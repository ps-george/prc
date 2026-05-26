"""Phase 2 — Correctness. Hunt for bugs.

The LLM is asked to return a JSON array of issues. Output is parsed
defensively: malformed entries are skipped and a warning issue is
emitted in their place rather than aborting the review.
"""

from __future__ import annotations

import json
import re

from prc.diff import Diff
from prc.llm import LLMClient
from prc.verdict import Category, Issue, Location, Severity

SYSTEM = (
    "You are a careful code reviewer hunting for real bugs. Look for: "
    "off-by-one errors, missing null/undefined paths, swallowed errors, "
    "race conditions, resource leaks, type confusion, injection or auth "
    "bypass, secret exposure.\n\n"
    "Return ONLY a JSON array. Each element has fields: severity "
    "('blocker'|'major'|'minor'), category ('correctness'|'security'|"
    "'performance'|'style'|'testing'|'other'), file (string), line "
    "(integer or null), title (short), detail (one paragraph), "
    "suggested_fix (short, optional).\n\n"
    "If there are no real issues, return []. Do not pad with surface "
    "nits — only flag things a serious reviewer would call out."
)


_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _extract_array(text: str) -> str:
    match = _JSON_ARRAY_RE.search(text)
    return match.group(0) if match else "[]"


def _parse_issues(raw: str) -> list[Issue]:
    text = _extract_array(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    issues: list[Issue] = []
    for idx, entry in enumerate(data):
        if not isinstance(entry, dict):
            continue
        try:
            issues.append(
                Issue(
                    id=f"c-{idx + 1}",
                    severity=Severity(entry.get("severity", "minor")),
                    category=Category(entry.get("category", "correctness")),
                    location=Location(
                        file=str(entry.get("file", "<unknown>")),
                        line=entry.get("line"),
                    ),
                    title=str(entry.get("title", "Untitled issue")),
                    detail=str(entry.get("detail", "")),
                    suggested_fix=entry.get("suggested_fix"),
                )
            )
        except (ValueError, TypeError):
            continue
    return issues


async def run(diff: Diff, summary: str, llm: LLMClient) -> list[Issue]:
    user_parts = [f"Summary of the change:\n{summary}", "Diff:"]
    for f in diff.files:
        user_parts.append(f"--- {f.path} ---\n{f.patch}")
    resp = await llm.complete(SYSTEM, [{"role": "user", "content": "\n\n".join(user_parts)}])
    return _parse_issues(resp.content)
