"""Driver — run prc and vanilla control on the same SWE-bench sample.

Writes two JSON result blobs into ``benchmarks/results/`` and prints a
combined summary table to stdout.

Usage::

    export PRC_MODEL=anthropic/claude-sonnet-4.6
    export PRC_API_KEY=$OPENROUTER_API_KEY
    export PRC_API_BASE=https://openrouter.ai/api/v1
    uv run python -m benchmarks.run_real_bugs
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from benchmarks.real_bugs import DATA_DIR, load_instances
from benchmarks.real_bugs import run_all as run_prc_all
from benchmarks.real_bugs import summarise as summarise_prc
from benchmarks.vanilla_control import run_all as run_vanilla_all
from benchmarks.vanilla_control import summarise as summarise_vanilla
from prc.llm import client_from_env

RESULTS_DIR = Path(__file__).parent / "results"


async def main_async() -> None:
    sample = DATA_DIR / "sample_20.json"
    instances = load_instances(sample)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")

    if os.environ.get("PRC_MODEL") is None:
        raise SystemExit("Set PRC_MODEL (and PRC_API_KEY/PRC_API_BASE) to run.")

    print(f"== running prc (reversed = real bugs) on {len(instances)} ==", flush=True)
    t0 = time.monotonic()
    prc_results = await run_prc_all(
        instances, client_from_env, direction="reversed", tag="prc"
    )
    prc_secs = time.monotonic() - t0
    prc_summary = summarise_prc(prc_results)
    prc_summary["wall_seconds"] = prc_secs

    print(f"== running vanilla control on {len(instances)} instances ==", flush=True)
    t0 = time.monotonic()
    vanilla_results = await run_vanilla_all(instances, client_from_env)
    vanilla_secs = time.monotonic() - t0
    vanilla_summary = summarise_vanilla(vanilla_results)
    vanilla_summary["wall_seconds"] = vanilla_secs

    print(f"== running prc (forward = real fixes, FP control) on {len(instances)} ==",
          flush=True)
    t0 = time.monotonic()
    prc_fp_results = await run_prc_all(
        instances, client_from_env, direction="forward", tag="prc-fp"
    )
    prc_fp_secs = time.monotonic() - t0
    prc_fp_summary = summarise_prc(prc_fp_results)
    prc_fp_summary["wall_seconds"] = prc_fp_secs
    # On forward patches, "caught" is the FALSE POSITIVE rate
    prc_fp_summary["false_positive_rate"] = prc_fp_summary["recall"]

    out = {
        "stamp": stamp,
        "model": os.environ["PRC_MODEL"],
        "api_base": os.environ.get("PRC_API_BASE", ""),
        "n_instances": len(instances),
        "prc": prc_summary,
        "vanilla": vanilla_summary,
        "prc_forward_fp_control": prc_fp_summary,
    }
    blob_path = RESULTS_DIR / f"real-bugs-{stamp}.json"
    blob_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"wrote {blob_path}")

    print()
    print("=" * 60)
    print(f"prc:        recall={prc_summary['recall']:.2%}  "
          f"caught={prc_summary['caught']}/{prc_summary['n']}  "
          f"errors={prc_summary['errors']}  "
          f"wall={prc_secs:.1f}s")
    print(f"vanilla:    recall={vanilla_summary['recall']:.2%}  "
          f"caught={vanilla_summary['caught']}/{vanilla_summary['n']}  "
          f"errors={vanilla_summary['errors']}  "
          f"wall={vanilla_secs:.1f}s")
    print(f"prc-fp:     fp-rate={prc_fp_summary['false_positive_rate']:.2%}  "
          f"flagged={prc_fp_summary['caught']}/{prc_fp_summary['n']}  "
          f"wall={prc_fp_secs:.1f}s")
    print("=" * 60)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
