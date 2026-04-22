#!/usr/bin/env python3
"""PushPilot eval script — variance-aware, N=3 runs per scenario.

Tests PushPilot's gate-6 timing judgment using synthetic PersonalizedBriefs
with controlled priority, digest_opt_in, and volume signals.

Key risk to watch: agent second-guessing itself and returning HOLD_UNTIL when
SEND_NOW is warranted (doing the code's job, not its own). This is the failure
mode that breaks the calibration loop.

Usage:
    python scripts/eval_pushpilot.py              # uses ANTHROPIC_API_KEY
    PULSECRAFT_RUN_LLM_TESTS=1 python scripts/eval_pushpilot.py

Writes report to audit/eval/pushpilot-<timestamp>.txt.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


# Load .env before imports that check ANTHROPIC_API_KEY
def _load_env() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


_load_env()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pulsecraft.agents.pushpilot import (  # noqa: E402
    AgentInvocationError,
    AgentOutputValidationError,
    PushPilot,
)
from pulsecraft.config.loader import get_bu_profile  # noqa: E402
from pulsecraft.schemas.decision import Decision, DecisionAgent, DecisionVerb  # noqa: E402
from pulsecraft.schemas.personalized_brief import (  # noqa: E402
    MessageQuality,
    MessageVariants,
    PersonalizedBrief,
    Priority,
    RecommendedAction,
    Relevance,
)
from pulsecraft.schemas.personalized_brief import ProducedBy as PBProducedBy  # noqa: E402

AUDIT_DIR = Path(__file__).parent.parent / "audit" / "eval"

RUNS_PER_SCENARIO = 3

# Eval scenarios: (name, bu_id, priority, digest_opt_in_override, expected_decisions, description)
# expected_decisions: set of acceptable terminal verbs
# "close" decisions = semantically equivalent (SEND_NOW ≈ acceptable when policy allows)
_SCENARIOS = [
    {
        "name": "P1 + working hours + low volume",
        "bu_id": "bu_alpha",
        "priority": Priority.P1,
        "expected": {"send_now", "hold_until"},  # SEND_NOW preferred; HOLD_UNTIL acceptable
        "risky_if": {"digest"},  # DIGEST is wrong for P1
        "description": "P1 priority, low volume, no special signals → SEND_NOW or HOLD_UNTIL",
    },
    {
        "name": "P2 + digest opt-in (bu_alpha)",
        "bu_id": "bu_alpha",  # digest_opt_in: true
        "priority": Priority.P2,
        "expected": {"digest", "hold_until", "send_now"},
        "risky_if": set(),
        "description": "P2 + BU has digest_opt_in=true → DIGEST is expected format",
    },
    {
        "name": "P0 + working hours",
        "bu_id": "bu_alpha",
        "priority": Priority.P0,
        "expected": {"send_now", "hold_until"},  # P0 → strong signal for SEND_NOW
        "risky_if": {"digest"},
        "description": "P0 priority → SEND_NOW unless quiet hours (code enforces quiet-hours override)",
    },
    {
        "name": "P1 + no digest opt-in (bu_beta)",
        "bu_id": "bu_beta",  # digest_opt_in: false, email only
        "priority": Priority.P1,
        "expected": {"send_now", "hold_until"},
        "risky_if": {"digest"},
        "description": "P1 + no digest opt-in → SEND_NOW or HOLD_UNTIL; DIGEST would be wrong",
    },
    {
        "name": "P2 + no digest opt-in (bu_beta)",
        "bu_id": "bu_beta",  # digest_opt_in: false
        "priority": Priority.P2,
        "expected": {"send_now", "hold_until", "digest"},
        "risky_if": set(),
        "description": "P2 + no digest opt-in → SEND_NOW or HOLD_UNTIL (DIGEST less expected but acceptable)",
    },
]


def _make_personalized_brief(bu_id: str, priority: Priority) -> PersonalizedBrief:
    now = datetime.now(UTC)
    agent = DecisionAgent(name="buatlas", version="1.0")
    return PersonalizedBrief(
        personalized_brief_id=str(uuid.uuid4()),
        change_id=str(uuid.uuid4()),
        brief_id=str(uuid.uuid4()),
        bu_id=bu_id,
        produced_at=now,
        produced_by=PBProducedBy(version="1.0", invocation_id=str(uuid.uuid4())),
        relevance=Relevance.AFFECTED,
        priority=priority,
        why_relevant="BU affected by prior authorization form changes. Field reps will see new required fields.",
        recommended_actions=[
            RecommendedAction(
                owner="BU head",
                action="Brief field representatives before rollout.",
                by_when="2026-05-15",
            )
        ],
        assumptions=["Standard US rollout applies."],
        message_variants=MessageVariants(
            push_short="PA form updated: new fields required for specialty pharmacy.",
            teams_medium="Prior authorization form now requires additional clinical justification. Prepare field team before May rollout.",
            email_long="Starting May 2026, the prior authorization form introduces mandatory clinical justification fields. Field representatives will need briefing before the rollout date.",
        ),
        message_quality=MessageQuality.WORTH_SENDING,
        confidence_score=0.87,
        decisions=[
            Decision(
                gate=4,
                verb=DecisionVerb.AFFECTED,
                reason="BU owns PA workflow.",
                confidence=0.87,
                decided_at=now,
                agent=agent,
            ),
            Decision(
                gate=5,
                verb=DecisionVerb.WORTH_SENDING,
                reason="Clear action required.",
                confidence=0.86,
                decided_at=now,
                agent=agent,
            ),
        ],
        regeneration_attempts=0,
    )


def _classify_run(actual: str, expected: set[str], risky_if: set[str]) -> str:
    if actual in risky_if:
        return "risk"
    if actual in expected:
        return "match"
    return "mismatch"


def main() -> None:
    now_str = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    model = "claude-sonnet-4-6"
    print(
        f"\nPushPilot Eval Report (model: {model}, runs per scenario: {RUNS_PER_SCENARIO}, "
        f"date: {datetime.now(UTC).strftime('%Y-%m-%d')})\n",
        flush=True,
    )

    pp = PushPilot()

    total_latency = 0.0
    issues: list[str] = []
    report_lines: list[str] = []

    for scenario in _SCENARIOS:
        sep = "─" * 77
        header = f"\nScenario: {scenario['name']}"
        print(sep)
        print(header)
        print(f"  BU: {scenario['bu_id']}  Priority: {scenario['priority']}")
        print(f"  {scenario['description']}")
        print(sep)
        report_lines += [sep, header, sep]
        report_lines.append(f"  BU: {scenario['bu_id']}  Priority: {scenario['priority']}")

        bu_profile = get_bu_profile(scenario["bu_id"])
        pb = _make_personalized_brief(scenario["bu_id"], scenario["priority"])

        decisions_seen: list[str] = []
        run_classifications: list[str] = []

        for run_n in range(1, RUNS_PER_SCENARIO + 1):
            print(f"    Run {run_n}/{RUNS_PER_SCENARIO}...", end=" ", flush=True)
            t0 = time.monotonic()
            try:
                result = pp.invoke(pb, bu_profile)
                elapsed = time.monotonic() - t0
                total_latency += elapsed
                decision_str = str(result.decision)
                channel_str = str(result.channel) if result.channel else "null"
                classification = _classify_run(
                    decision_str, scenario["expected"], scenario["risky_if"]
                )
                decisions_seen.append(decision_str)
                run_classifications.append(classification)
                print(
                    f"decision={decision_str} channel={channel_str} ({elapsed:.1f}s) [{classification}]"
                )
            except (AgentInvocationError, AgentOutputValidationError, Exception) as exc:
                elapsed = time.monotonic() - t0
                total_latency += elapsed
                decisions_seen.append("ERROR")
                run_classifications.append("error")
                print(f"ERROR: {type(exc).__name__}: {str(exc)[:80]}")

        # Summarise
        counter = Counter(decisions_seen)
        all_match = all(c == "match" for c in run_classifications)
        any_risk = any(c == "risk" for c in run_classifications)
        any_mismatch = any(c == "mismatch" for c in run_classifications)
        any_error = any(c == "error" for c in run_classifications)
        stable = len(counter) == 1

        decision_str = ", ".join(f"{v}({n}/{RUNS_PER_SCENARIO})" for v, n in counter.most_common())

        if any_risk:
            status = f"⚠️  RISK — agent chose {counter.most_common(1)[0][0]} (expected {scenario['expected']})"
            issues.append(f"{scenario['name']}: risk decision ({decision_str})")
        elif any_mismatch or any_error:
            status = f"❌  mismatch/error — {decision_str}"
            issues.append(f"{scenario['name']}: mismatch/error ({decision_str})")
        elif all_match and stable:
            status = "✅  stable match"
        elif all_match:
            status = "✅  acceptable variance"
        else:
            status = "🟡  unstable"
            issues.append(f"{scenario['name']}: unstable across runs ({decision_str})")

        stability = "✅ stable" if stable else "🟡 unstable"
        summary = (
            f"  Decisions: {decision_str:50s}  {stability}\n"
            f"  Expected:  {str(scenario['expected'])}\n"
            f"  Status:    {status}"
        )
        print(summary)
        report_lines.append(summary)

    # Footer
    footer = (
        f"\n{'─' * 77}\n"
        f"Total scenarios: {len(_SCENARIOS)} × {RUNS_PER_SCENARIO} runs = "
        f"{len(_SCENARIOS) * RUNS_PER_SCENARIO} invocations\n"
        f"Total latency: {total_latency:.1f}s\n"
    )
    print(footer)
    report_lines.append(footer)

    if issues:
        issues_block = "Items worth reviewing:\n" + "\n".join(f"  - {i}" for i in issues)
        print(issues_block)
        report_lines.append(issues_block)
    else:
        ok_msg = "No issues — all scenarios stable and matching expected decisions."
        print(ok_msg)
        report_lines.append(ok_msg)

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = AUDIT_DIR / f"pushpilot-{now_str}.txt"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
