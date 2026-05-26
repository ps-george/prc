"""Verdict data types.

A review produces a :class:`Verdict` with a top-level decision and a
list of per-issue findings. Author-side response types
(:class:`AuthorResponse`) are defined here so callers can already build
against the shape; the interactive loop that consumes them ships in
v0.2.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    BLOCKER = "blocker"
    MAJOR = "major"
    MINOR = "minor"


class Category(StrEnum):
    CORRECTNESS = "correctness"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    TESTING = "testing"
    OTHER = "other"


class Location(BaseModel):
    model_config = ConfigDict(frozen=True)

    file: str
    line: int | None = None


class Issue(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    severity: Severity
    category: Category
    location: Location
    title: str
    detail: str
    suggested_fix: str | None = None


Decision = Literal["approve", "request_changes", "discuss"]


class Verdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: Decision
    summary: str
    issues: list[Issue] = Field(default_factory=list)

    def blockers(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.BLOCKER]

    def majors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.MAJOR]


# --- Author-side response types (data types only in v0.1.0) ---------------


AuthorAction = Literal["accept", "refute", "clarify"]


class AuthorResponse(BaseModel):
    """An author's substantive response to a single issue.

    A response is *substantive* iff its ``note`` carries content beyond a
    bare yes/no — the consumer in v0.2 will enforce this via
    :func:`is_substantive`.
    """

    model_config = ConfigDict(frozen=True)

    issue_id: str
    action: AuthorAction
    note: str


_SINGLE_WORD_REFUSALS = {
    "no", "nope", "wrong", "disagree", "lgtm", "fine", "ok", "okay", "sure", "yes",
}


def is_substantive(response: AuthorResponse) -> bool:
    """Reject single-word refusals; require some real content."""
    note = response.note.strip().lower().rstrip(".!")
    if not note:
        return False
    if note in _SINGLE_WORD_REFUSALS:
        return False
    return len(note.split()) >= 3
