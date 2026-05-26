"""Render a :class:`Verdict` as JSON."""

from __future__ import annotations

from prc.verdict import Verdict


def render(verdict: Verdict) -> str:
    return verdict.model_dump_json(indent=2)
