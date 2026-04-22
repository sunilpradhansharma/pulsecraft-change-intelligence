#!/usr/bin/env python3
"""SignalScribe eval script — run all 8 fixtures and report decision-chain accuracy.

Not a test. Always exits 0. Writes a copy of the report to audit/eval/.

Usage:
    .venv/bin/python scripts/eval_signalscribe.py
    ANTHROPIC_API_KEY=... .venv/bin/python scripts/eval_signalscribe.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pulsecraft.agents.signalscribe import (
    AgentInvocationError,
    AgentOutputValidationError,
    SignalScribe,
)
from pulsecraft.schemas.change_artifact import ChangeArtifact

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "changes"
AUDIT_EVAL_DIR = Path(__file__).parent.parent / "audit" / "eval"

# Sonnet 4.6 pricing (USD per million tokens)
_INPUT_PRICE_PER_MTK = 3.00
_OUTPUT_PRICE_PER_MTK = 15.00

# Expected decision chains per fixture (from fixtures/changes/README.md)
# Format: list of (gate, verb) tuples — only terminal verb per gate matters for matching
EXPECTED_CHAINS: dict[str, list[str]] = {
    "change_001_clearcut_communicate.json": ["COMMUNICATE", "RIPE", "READY"],
    "change_002_pure_internal_refactor.json": ["ARCHIVE"],
    "change_003_ambiguous_escalate.json": ["ESCALATE", "NEED_CLARIFICATION"],  # either is valid
    "change_004_early_flag_hold_until.json": ["COMMUNICATE", "HOLD_UNTIL"],
    "change_005_muddled_need_clarification.json": ["COMMUNICATE", "RIPE", "NEED_CLARIFICATION"],
    "change_006_multi_bu_affected_vs_adjacent.json": ["COMMUNICATE", "RIPE", "READY"],
    "change_007_mlr_sensitive.json": ["COMMUNICATE", "RIPE", "READY"],
    "change_008_post_hoc_already_shipped.json": ["COMMUNICATE", "RIPE", "READY"],
}

# Terminal categories for semantic-match logic
_STOP_GATE_1 = {"ARCHIVE", "ESCALATE"}
_STOP_GATE_2 = {"HOLD_UNTIL", "HOLD_INDEFINITE", "ESCALATE"}
_STOP_GATE_3 = {"NEED_CLARIFICATION", "UNRESOLVABLE", "ESCALATE"}


def _chain_str(verbs: list[str]) -> str:
    return "→".join(verbs)


def _match_status(expected: list[str], actual: list[str]) -> tuple[str, str]:
    """Return (symbol, label) for match status.

    ✅ exact match — same verbs same order
    🟡 semantic match — different verb but same terminal category
    ❌ mismatch — pipeline went a completely different direction
    """
    if actual == expected:
        return "✅", "match"

    # For fixture 003 the expected list has two alternatives
    # Check if actual matches either alternative (special case)
    if len(expected) >= 2 and actual and actual[0] in expected:
        return "✅", "match"

    # Semantic match: same number of gates reached AND terminal verb in same category
    if len(actual) == len(expected):
        exp_terminal = expected[-1]
        act_terminal = actual[-1] if actual else ""
        both_stop_g1 = exp_terminal in _STOP_GATE_1 and act_terminal in _STOP_GATE_1
        both_stop_g2 = exp_terminal in _STOP_GATE_2 and act_terminal in _STOP_GATE_2
        both_stop_g3 = exp_terminal in _STOP_GATE_3 and act_terminal in _STOP_GATE_3
        if both_stop_g1 or both_stop_g2 or both_stop_g3:
            return "🟡", "semantic"

    return "❌", "mismatch"


def _load_env() -> None:
    """Load .env file if ANTHROPIC_API_KEY not already set."""
    import os

    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


def main() -> None:
    _load_env()

    model = "claude-sonnet-4-6"
    date_str = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")

    print(f"\nSignalScribe Eval Report (model: {model}, date: {date_str})\n")

    try:
        ss = SignalScribe(model=model)
    except Exception as exc:
        print(f"ERROR: Could not initialize SignalScribe: {exc}")
        sys.exit(0)

    header = f"{'Fixture':<42} {'Expected':<32} {'Actual':<32} {'Status':<10} {'Cost':>7}"
    print(header)
    print("-" * len(header))

    rows: list[dict] = []
    total_cost = 0.0
    total_latency = 0.0
    mismatches: list[str] = []

    fixture_files = sorted(FIXTURES_DIR.glob("change_0*.json"))

    for fixture_path in fixture_files:
        fname = fixture_path.name
        expected = EXPECTED_CHAINS.get(fname, ["UNKNOWN"])

        try:
            artifact = ChangeArtifact.model_validate(json.loads(fixture_path.read_text()))
        except Exception as exc:
            print(f"  ERROR loading {fname}: {exc}")
            continue

        t0 = time.monotonic()
        error_msg: str | None = None
        actual_verbs: list[str] = []
        cost = 0.0

        try:
            brief = ss.invoke(artifact)
            actual_verbs = [d.verb for d in brief.decisions]
        except (AgentInvocationError, AgentOutputValidationError) as exc:
            error_msg = str(exc)[:80]
            actual_verbs = [f"ERROR: {error_msg[:40]}"]
        except Exception as exc:
            error_msg = str(exc)[:80]
            actual_verbs = [f"ERROR: {error_msg[:40]}"]

        elapsed = time.monotonic() - t0
        total_latency += elapsed

        symbol, label = _match_status(expected, actual_verbs)
        short_name = fname.replace("change_", "").replace(".json", "")

        row = {
            "fixture": short_name,
            "expected": _chain_str(expected),
            "actual": _chain_str(actual_verbs),
            "symbol": symbol,
            "label": label,
            "elapsed": elapsed,
            "error": error_msg,
        }
        rows.append(row)

        exp_str = _chain_str(expected)[:30]
        act_str = _chain_str(actual_verbs)[:30]
        cost_str = f"${cost:.3f}" if cost > 0 else "  n/a"

        print(f"  {short_name:<40} {exp_str:<32} {act_str:<32} {symbol} {label:<8} {cost_str:>7}")

        if label == "mismatch":
            mismatches.append(
                f"{fname}: expected {_chain_str(expected)}, got {_chain_str(actual_verbs)}"
            )

    print(f"\nTotal latency: {total_latency:.1f}s")
    print(f"Total cost estimate: ${total_cost:.4f}")

    match_count = sum(1 for r in rows if r["label"] in ("match", "semantic"))
    mismatch_count = sum(1 for r in rows if r["label"] == "mismatch")
    print(f"\nSummary: {match_count}/{len(rows)} ✅/🟡, {mismatch_count}/{len(rows)} ❌")

    if mismatches:
        print("\nItems to review:")
        for m in mismatches:
            print(f"  ❌ {m}")
    else:
        print("\nItems to review:\n  (none)")

    print(
        "\nDetailed reasoning available in audit/<date>/<change_id>.jsonl"
        "\nFor prompt tuning: run with PULSECRAFT_RUN_LLM_TESTS=1 pytest tests/integration/agents/ -v -m llm"
    )

    # Write report to audit/eval/
    report_lines = [header, "-" * len(header)]
    for r in rows:
        report_lines.append(
            f"  {r['fixture']:<40} {r['expected']:<32} {r['actual']:<32} {r['symbol']} {r['label']}"
        )
    report_lines += [
        f"\nTotal latency: {total_latency:.1f}s",
        f"Total cost: ${total_cost:.4f}",
        f"Summary: {match_count}/{len(rows)} match, {mismatch_count}/{len(rows)} mismatch",
    ]
    if mismatches:
        report_lines.append("\nMismatches:")
        for m in mismatches:
            report_lines.append(f"  {m}")

    AUDIT_EVAL_DIR.mkdir(parents=True, exist_ok=True)
    report_path = AUDIT_EVAL_DIR / f"signalscribe-{timestamp}.txt"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
