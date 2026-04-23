"""Produces structured markdown + JSON reports from eval results."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from pulsecraft.eval.runner import FixtureEvalResult

_CLASSIFICATION_SYMBOL = {
    "stable": "✅",
    "acceptable_variance": "✅",
    "unstable": "🟡",
    "false_positive_risk": "⚠️",
    "mismatch": "❌",
}

_CLASSIFICATION_LABEL = {
    "stable": "stable",
    "acceptable_variance": "acceptable variance",
    "unstable": "unstable",
    "false_positive_risk": "FALSE POSITIVE RISK",
    "mismatch": "mismatch",
}


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _fixture_short(fixture: str) -> str:
    return fixture.replace("change_", "").replace(".json", "")


def _dist_str(verb_distribution: dict[str, int], n: int) -> str:
    if not verb_distribution:
        return "—"
    return " / ".join(
        f"{v}({c}/{n})" for v, c in sorted(verb_distribution.items(), key=lambda x: -x[1])
    )


def write_agent_report(
    results: list[FixtureEvalResult],
    agent_name: str,
    n_runs: int,
    out_dir: Path,
    model: str = "claude-sonnet-4-6",
) -> tuple[Path, Path]:
    """Write report.md + summary.json to out_dir. Return (md_path, json_path)."""
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).isoformat(timespec="seconds") + "Z"
    sha = _git_sha()

    # ------------------------------------------------------------------ JSON
    fixtures_data = []
    for r in results:
        fixtures_data.append(
            {
                "fixture": r.fixture,
                "bu_id": r.bu_id,
                "verb_distribution": r.verb_distribution,
                "classification": r.classification,
                "skipped": r.skipped,
                "skip_reason": r.skip_reason if r.skipped else None,
                "cost_usd": round(r.total_cost_usd, 4),
                "elapsed_s": round(r.total_elapsed_s, 1),
                "runs": [
                    {
                        "run_index": run.run_index,
                        "terminal_verb": run.terminal_verb,
                        "secondary_verb": run.secondary_verb,
                        "confidence": run.confidence,
                        "elapsed_s": round(run.elapsed_s, 1),
                        "cost_usd": round(run.cost_usd, 4),
                        "error": run.error,
                    }
                    for run in r.runs
                ],
                "expected_terminal_verbs": sorted(r.expected.expected_terminal_verbs),
                "acceptable_alternate_verbs": sorted(r.expected.acceptable_alternate_verbs),
                "false_positive_verbs": sorted(r.expected.false_positive_verbs),
                "notes": r.expected.notes,
            }
        )

    totals = {
        c: 0
        for c in ("stable", "acceptable_variance", "unstable", "false_positive_risk", "mismatch")
    }
    for r in results:
        if not r.skipped:
            totals[r.classification] = totals.get(r.classification, 0) + 1
    skipped_count = sum(1 for r in results if r.skipped)

    summary_obj = {
        "agent": agent_name,
        "timestamp": timestamp,
        "commit": sha,
        "model": model,
        "runs_per_fixture": n_runs,
        "fixtures": fixtures_data,
        "totals": totals,
        "skipped": skipped_count,
        "total_cost_usd": round(sum(r.total_cost_usd for r in results), 4),
        "total_elapsed_s": round(sum(r.total_elapsed_s for r in results), 1),
    }

    json_path = out_dir / f"summary_{agent_name}.json"
    json_path.write_text(json.dumps(summary_obj, indent=2), encoding="utf-8")

    # ---------------------------------------------------------------- Markdown
    lines: list[str] = [
        f"# PulseCraft Eval Report — {agent_name.title()}",
        "",
        f"**Timestamp:** {timestamp}  ",
        f"**Commit:** {sha}  ",
        f"**Model:** {model}  ",
        f"**Runs per fixture:** {n_runs}  ",
        "",
        "---",
        "",
        "## Summary",
        "",
    ]

    # Summary table
    header = "| Fixture | Bu | Expected | Observed | Classification | Cost |"
    sep = "|---|---|---|---|---|---|"
    lines += [header, sep]
    for r in results:
        fname = _fixture_short(r.fixture)
        bu = r.bu_id or "—"
        expected_str = "{" + ", ".join(sorted(r.expected.expected_terminal_verbs)) + "}"
        if r.skipped:
            observed_str = f"SKIPPED — {r.skip_reason[:40]}"
            cls_str = "⏭️ skipped"
        else:
            observed_str = _dist_str(r.verb_distribution, n_runs)
            sym = _CLASSIFICATION_SYMBOL[r.classification]
            lbl = _CLASSIFICATION_LABEL[r.classification]
            cls_str = f"{sym} {lbl}"
        cost_str = f"${r.total_cost_usd:.3f}"
        lines.append(
            f"| {fname} | {bu} | {expected_str} | {observed_str} | {cls_str} | {cost_str} |"
        )

    lines += [""]

    # Totals
    non_skipped = [r for r in results if not r.skipped]
    totals_line = "  ".join(
        f"**{_CLASSIFICATION_LABEL[k]}:** {totals[k]}"
        for k in ("stable", "acceptable_variance", "unstable", "false_positive_risk", "mismatch")
    )
    lines += [
        f"**Overall ({len(non_skipped)} evaluated, {skipped_count} skipped):** {totals_line}  ",
        f"**Total cost:** ${summary_obj['total_cost_usd']:.3f}  ",
        f"**Total elapsed:** {summary_obj['total_elapsed_s']:.0f}s  ",
        "",
        "---",
        "",
        "## Detail",
        "",
    ]

    # Per-fixture detail
    for r in results:
        fname = _fixture_short(r.fixture)
        bu_suffix = f" / {r.bu_id}" if r.bu_id else ""
        lines.append(f"### {fname}{bu_suffix}")
        lines += [
            "",
            f"- **Expected terminal verbs:** {sorted(r.expected.expected_terminal_verbs)}",
        ]
        if r.expected.acceptable_alternate_verbs:
            lines.append(
                f"- **Acceptable alternates:** {sorted(r.expected.acceptable_alternate_verbs)}"
            )
        if r.expected.false_positive_verbs:
            lines.append(f"- **False-positive verbs:** {sorted(r.expected.false_positive_verbs)}")

        if r.skipped:
            lines += [
                "- **Classification:** ⏭️ SKIPPED",
                f"- **Reason:** {r.skip_reason}",
            ]
        else:
            sym = _CLASSIFICATION_SYMBOL[r.classification]
            lbl = _CLASSIFICATION_LABEL[r.classification]
            lines += [
                f"- **Observed distribution:** {_dist_str(r.verb_distribution, n_runs)}",
                f"- **Classification:** {sym} **{lbl}**",
            ]
            # Per-run table
            lines += [
                "",
                "| Run | Terminal | Secondary | Confidence | Elapsed | Cost | Error |",
                "|---|---|---|---|---|---|---|",
            ]
            for run in r.runs:
                conf = f"{run.confidence:.2f}" if run.confidence is not None else "—"
                sec = run.secondary_verb or "—"
                err = (run.error or "")[:30] if run.error else "—"
                lines.append(
                    f"| {run.run_index} | {run.terminal_verb or 'ERROR'} | {sec} | {conf} | "
                    f"{run.elapsed_s:.1f}s | ${run.cost_usd:.3f} | {err} |"
                )

        if r.expected.notes:
            lines += [
                "",
                f"> **Note:** {r.expected.notes}",
            ]
        lines += ["", "---", ""]

    md_path = out_dir / f"report_{agent_name}.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return md_path, json_path
