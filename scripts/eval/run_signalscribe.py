#!/usr/bin/env python3
"""Run the SignalScribe eval harness.

Usage:
    .venv/bin/python scripts/eval/run_signalscribe.py
    .venv/bin/python scripts/eval/run_signalscribe.py --runs 5
    .venv/bin/python scripts/eval/run_signalscribe.py --out-dir audit/eval/my-run

Exit 0 if all results are stable or acceptable_variance.
Exit 1 if any mismatch or false_positive_risk.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from pulsecraft.eval.expectations import EXPECTATIONS
from pulsecraft.eval.reporter import write_agent_report
from pulsecraft.eval.runner import run_agent_eval

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures" / "changes"


def main() -> int:
    parser = argparse.ArgumentParser(description="SignalScribe eval harness")
    parser.add_argument("--runs", type=int, default=3, metavar="N")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: audit/eval/<timestamp>)",
    )
    args = parser.parse_args()

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out_dir or Path("audit/eval") / ts

    expectations = [e for e in EXPECTATIONS if e.agent == "signalscribe"]
    print(
        f"\nSignalScribe eval — {len(expectations)} fixtures, {args.runs} runs each"
        f"\nOutput: {out_dir}\n"
    )

    results = []
    for expected in expectations:
        fixture_path = FIXTURES_DIR / expected.fixture
        short = expected.fixture.replace("change_", "").replace(".json", "")
        print(f"  [{short}] ...", end=" ", flush=True)
        result = run_agent_eval(expected, fixture_path, n_runs=args.runs)
        results.append(result)
        from pulsecraft.eval.reporter import _CLASSIFICATION_SYMBOL, _dist_str

        sym = _CLASSIFICATION_SYMBOL[result.classification]
        dist = _dist_str(result.verb_distribution, args.runs)
        print(f"{sym} {result.classification} — {dist}  (${result.total_cost_usd:.3f})")

    md_path, json_path = write_agent_report(results, "signalscribe", args.runs, out_dir)
    print(f"\nReport: {md_path}")
    print(f"JSON:   {json_path}")

    bad = [
        r
        for r in results
        if not r.skipped and r.classification in ("mismatch", "false_positive_risk")
    ]
    if bad:
        print(f"\n⚠️  {len(bad)} result(s) require attention:")
        for r in bad:
            print(f"  {r.classification}: {r.fixture} — {r.verb_distribution}")
        return 1
    print("\n✅ All results stable or acceptable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
