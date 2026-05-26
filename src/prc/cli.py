"""Command-line entry point.

Usage:
    prc <git-ref> [--mode quick] [--model MODEL] [--format md|json]

v0.1.0 supports ``--mode quick`` only. If ``PRC_MOCK=1`` is set, a
fixed mock review is emitted instead of calling out to an LLM — useful
for smoke tests and CI.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from prc import __version__
from prc.diff import parse_ref
from prc.llm import LLMClient, MockLLMClient, client_from_env
from prc.output import json_out, markdown
from prc.pipeline import review_quick


def _mock_client() -> LLMClient:
    mock = MockLLMClient()
    mock.queue(
        "This change refactors the X module. It touches two files and "
        "introduces a new helper. No tests added."
    )
    mock.queue(
        '[{"severity":"minor","category":"testing","file":"src/x.py",'
        '"line":42,"title":"No tests for new helper",'
        '"detail":"The new helper has no direct coverage.",'
        '"suggested_fix":"Add a unit test for the helper."}]'
    )
    return mock


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="prc",
        description=(
            "PR critic — a small, model-agnostic code review tool. "
            "Reviews a git ref and emits a structured verdict."
        ),
    )
    p.add_argument("ref", help="Git ref to review (e.g. HEAD, abc123, branch-name).")
    p.add_argument(
        "--mode", choices=["quick"], default="quick",
        help="Review mode. v0.1.0 supports 'quick' only.",
    )
    p.add_argument(
        "--model", default=None,
        help="Override the PRC_MODEL env var for this run.",
    )
    p.add_argument(
        "--format", choices=["md", "json"], default="md",
        help="Output format. Default: md.",
    )
    p.add_argument(
        "--repo", default=None, type=Path,
        help="Path to the git repository (defaults to current directory).",
    )
    p.add_argument("--version", action="version", version=f"prc {__version__}")
    return p


async def _run(args: argparse.Namespace) -> int:
    diff = parse_ref(args.ref, repo=args.repo)
    if os.environ.get("PRC_MOCK") == "1":
        llm: LLMClient = _mock_client()
    else:
        if args.model:
            os.environ["PRC_MODEL"] = args.model
        llm = client_from_env()
    verdict = await review_quick(diff, llm)
    if args.format == "json":
        sys.stdout.write(json_out.render(verdict))
    else:
        sys.stdout.write(markdown.render(verdict, ref=args.ref))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except (RuntimeError, NotImplementedError) as exc:
        print(f"prc: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
