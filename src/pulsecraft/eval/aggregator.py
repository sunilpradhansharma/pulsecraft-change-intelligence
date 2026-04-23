"""Aggregate per-agent summary.json files into a combined report."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


def write_aggregate_report(
    summary_paths: list[Path],
    out_dir: Path,
) -> tuple[Path, Path]:
    """Read per-agent summary.json files; write aggregate.md + aggregate.json.

    Returns (md_path, json_path).
    """
    summaries = [json.loads(p.read_text()) for p in summary_paths if p.exists()]
    if not summaries:
        raise ValueError("No summary files found")

    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat(timespec="seconds") + "Z"

    # Build aggregate data
    all_fixtures = []
    grand_totals = {
        "stable": 0,
        "acceptable_variance": 0,
        "unstable": 0,
        "false_positive_risk": 0,
        "mismatch": 0,
    }
    grand_skipped = 0
    grand_cost = 0.0
    grand_elapsed = 0.0

    for s in summaries:
        for f in s.get("fixtures", []):
            f["_agent"] = s["agent"]
        all_fixtures.extend(s.get("fixtures", []))
        for k in grand_totals:
            grand_totals[k] += s.get("totals", {}).get(k, 0)
        grand_skipped += s.get("skipped", 0)
        grand_cost += s.get("total_cost_usd", 0.0)
        grand_elapsed += s.get("total_elapsed_s", 0.0)

    aggregate_json = {
        "timestamp": timestamp,
        "agents": [s["agent"] for s in summaries],
        "runs_per_fixture": summaries[0].get("runs_per_fixture", 3) if summaries else 3,
        "model": summaries[0].get("model", "claude-sonnet-4-6") if summaries else "unknown",
        "per_agent_summaries": summaries,
        "grand_totals": grand_totals,
        "grand_skipped": grand_skipped,
        "grand_total_cost_usd": round(grand_cost, 4),
        "grand_total_elapsed_s": round(grand_elapsed, 1),
        "pass_criteria": {
            "no_false_positive_risk": grand_totals["false_positive_risk"] == 0,
            "no_mismatch": grand_totals["mismatch"] == 0,
            "overall_pass": (
                grand_totals["false_positive_risk"] == 0 and grand_totals["mismatch"] == 0
            ),
        },
    }

    json_path = out_dir / "aggregate.json"
    json_path.write_text(json.dumps(aggregate_json, indent=2), encoding="utf-8")

    # Markdown aggregate report
    lines: list[str] = [
        "# PulseCraft Eval — Aggregate Report",
        "",
        f"**Timestamp:** {timestamp}  ",
        f"**Model:** {aggregate_json['model']}  ",
        f"**Runs per fixture:** {aggregate_json['runs_per_fixture']}  ",
        f"**Agents evaluated:** {', '.join(aggregate_json['agents'])}  ",  # type: ignore[arg-type]
        "",
        "---",
        "",
        "## Overall results",
        "",
    ]

    # Grand totals table
    evaluated = sum(grand_totals.values())
    pass_icon = "✅" if aggregate_json["pass_criteria"]["overall_pass"] else "❌"  # type: ignore[index,call-overload]
    lines += [
        f"**Pass gate:** {pass_icon} (0 false_positive_risk + 0 mismatch required)  ",
        "",
        "| Classification | Count |",
        "|---|---|",
        f"| ✅ stable | {grand_totals['stable']} |",
        f"| ✅ acceptable variance | {grand_totals['acceptable_variance']} |",
        f"| 🟡 unstable | {grand_totals['unstable']} |",
        f"| ⚠️ FALSE POSITIVE RISK | {grand_totals['false_positive_risk']} |",
        f"| ❌ mismatch | {grand_totals['mismatch']} |",
        f"| ⏭️ skipped | {grand_skipped} |",
        "",
        f"**Total evaluated:** {evaluated}  ",
        f"**Total cost:** ${grand_cost:.3f}  ",
        f"**Total elapsed:** {grand_elapsed:.0f}s (~{grand_elapsed / 60:.1f} min)  ",
        "",
        "---",
        "",
        "## Per-agent summary",
        "",
    ]

    for s in summaries:
        agent = s["agent"]
        t = s.get("totals", {})
        n = s.get("runs_per_fixture", 3)
        agent_evaluated = sum(t.values())
        agent_skipped = s.get("skipped", 0)
        lines += [
            f"### {agent.title()}",
            "",
            f"Evaluated {agent_evaluated} cases ({agent_skipped} skipped), {n} runs each:  ",
            f"stable={t.get('stable', 0)} / acceptable={t.get('acceptable_variance', 0)} / "
            f"unstable={t.get('unstable', 0)} / fp_risk={t.get('false_positive_risk', 0)} / "
            f"mismatch={t.get('mismatch', 0)}  ",
            f"Cost: ${s.get('total_cost_usd', 0):.3f}  Elapsed: {s.get('total_elapsed_s', 0):.0f}s  ",
            "",
        ]

    # Flag mismatches and false positives
    problems = [
        f
        for f in all_fixtures
        if not f.get("skipped") and f.get("classification") in ("mismatch", "false_positive_risk")
    ]
    if problems:
        lines += [
            "---",
            "",
            "## Items requiring attention",
            "",
        ]
        for f in problems:
            cls = f["classification"]
            sym = "⚠️" if cls == "false_positive_risk" else "❌"
            fname = f["fixture"].replace("change_", "").replace(".json", "")
            bu = f" / {f['bu_id']}" if f.get("bu_id") else ""
            dist = " / ".join(f"{v}({c})" for v, c in f.get("verb_distribution", {}).items())
            lines += [
                f"**{sym} {f['_agent']} — {fname}{bu}**  ",
                f"Expected: {f['expected_terminal_verbs']}  ",
                f"Observed: {dist}  ",
                f"Classification: {cls}  ",
                f"Note: {f.get('notes', '')[:200]}  ",
                "",
            ]

    md_path = out_dir / "aggregate.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return md_path, json_path
