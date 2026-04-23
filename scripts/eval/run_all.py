#!/usr/bin/env python3
"""Run all three agent evals sequentially and produce a combined aggregate report.

Usage:
    .venv/bin/python scripts/eval/run_all.py
    .venv/bin/python scripts/eval/run_all.py --runs 3 --out-dir audit/eval/2026-04-23-baseline

Exit 0 if all results are stable or acceptable_variance.
Exit 1 if any mismatch or false_positive_risk across any agent.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from pulsecraft.eval.aggregator import write_aggregate_report
from pulsecraft.eval.expectations import EXPECTATIONS
from pulsecraft.eval.reporter import _CLASSIFICATION_SYMBOL, _dist_str, write_agent_report
from pulsecraft.eval.runner import run_agent_eval

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures" / "changes"


def _run_agent(agent_name: str, n_runs: int, out_dir: Path) -> list:
    expectations = [e for e in EXPECTATIONS if e.agent == agent_name]
    print(f"\n{'=' * 60}")
    print(f"  {agent_name.upper()} — {len(expectations)} cases, {n_runs} runs each")
    print(f"{'=' * 60}")

    results = []
    for expected in expectations:
        fixture_path = FIXTURES_DIR / expected.fixture
        short = expected.fixture.replace("change_", "").replace(".json", "")
        bu = f" / {expected.bu_id}" if expected.bu_id else ""
        label = f"[{short}{bu}]"
        print(f"  {label} ...", end=" ", flush=True)
        result = run_agent_eval(expected, fixture_path, n_runs=n_runs)
        results.append(result)
        if result.skipped:
            print(f"⏭️ SKIPPED — {result.skip_reason[:60]}")
        else:
            sym = _CLASSIFICATION_SYMBOL[result.classification]
            dist = _dist_str(result.verb_distribution, n_runs)
            print(f"{sym} {result.classification} — {dist}  (${result.total_cost_usd:.3f})")

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all PulseCraft agent evals")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output dir (default: audit/eval/<timestamp>)",
    )
    args = parser.parse_args()

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out_dir or Path("audit/eval") / ts

    print(f"\nPulseCraft full eval — model: claude-sonnet-4-6, runs: {args.runs}")
    print(f"Output: {out_dir}\n")

    all_results = []
    summary_paths = []

    for agent in ("signalscribe", "buatlas", "pushpilot"):
        results = _run_agent(agent, args.runs, out_dir)
        all_results.extend(results)
        _, json_path = write_agent_report(results, agent, args.runs, out_dir)
        summary_paths.append(json_path)

    # Aggregate
    agg_md, agg_json = write_aggregate_report(summary_paths, out_dir)

    print(f"\n{'=' * 60}")
    print("  AGGREGATE RESULTS")
    print(f"{'=' * 60}")

    import json as _json

    agg = _json.loads(agg_json.read_text())
    gt = agg["grand_totals"]
    print(
        f"  stable={gt['stable']}  acceptable={gt['acceptable_variance']}  "
        f"unstable={gt['unstable']}  fp_risk={gt['false_positive_risk']}  "
        f"mismatch={gt['mismatch']}  skipped={agg['grand_skipped']}"
    )
    print(f"  Total cost: ${agg['grand_total_cost_usd']:.3f}")
    print(
        f"  Total elapsed: {agg['grand_total_elapsed_s']:.0f}s ({agg['grand_total_elapsed_s'] / 60:.1f} min)"
    )
    print(f"\n  Aggregate report: {agg_md}")
    print(f"  Aggregate JSON:   {agg_json}")

    pass_gate = agg["pass_criteria"]["overall_pass"]
    if pass_gate:
        print("\n✅ PASS — no false_positive_risk, no mismatch")
        return 0
    else:
        print(f"\n❌ FAIL — fp_risk={gt['false_positive_risk']}, mismatch={gt['mismatch']}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
