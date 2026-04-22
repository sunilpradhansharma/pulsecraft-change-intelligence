"""Policy config sanity checks: thresholds in range, no empty terms, known HITL triggers."""

from __future__ import annotations

from pulsecraft.config import get_policy
from pulsecraft.schemas.policy import ConfidenceThresholds

KNOWN_HITL_TRIGGERS = {
    "any_agent_escalate",
    "gate_3_need_clarification",
    "gate_3_unresolvable",
    "confidence_below_threshold",
    "priority_p0",
    "draft_contains_commitment_or_date",
    "restricted_term_detected",
    "mlr_sensitive_content_detected",
    "second_weak_from_gate_5",
    "dedupe_or_rate_limit_conflict_requiring_judgment",
}


def _all_threshold_values(thresholds: ConfidenceThresholds) -> list[tuple[str, float]]:
    ss = thresholds.signalscribe
    ba = thresholds.buatlas
    pp = thresholds.pushpilot
    return [
        ("signalscribe.gate_1_communicate", ss.gate_1_communicate),
        ("signalscribe.gate_1_archive", ss.gate_1_archive),
        ("signalscribe.gate_2_ripe", ss.gate_2_ripe),
        ("signalscribe.gate_3_ready", ss.gate_3_ready),
        ("buatlas.gate_4_affected", ba.gate_4_affected),
        ("buatlas.gate_4_any", ba.gate_4_any),
        ("buatlas.gate_5_worth_sending", ba.gate_5_worth_sending),
        ("pushpilot.gate_6_any", pp.gate_6_any),
    ]


def test_all_confidence_thresholds_in_unit_interval() -> None:
    for name, value in _all_threshold_values(get_policy().confidence_thresholds):
        assert 0.0 <= value <= 1.0, f"Threshold {name}={value} is outside [0, 1]"


def test_no_restricted_term_is_empty_string() -> None:
    rt = get_policy().restricted_terms
    all_terms = rt.commitments_and_dates + rt.scientific_communication + rt.sensitive_data_markers
    for term in all_terms:
        assert term.strip() != "", "Empty string found in restricted_terms"


def test_hitl_triggers_are_from_known_set() -> None:
    for trigger in get_policy().hitl_triggers:
        assert trigger in KNOWN_HITL_TRIGGERS, (
            f"Unknown HITL trigger {trigger!r}. Known: {sorted(KNOWN_HITL_TRIGGERS)}"
        )


def test_rate_limits_are_positive() -> None:
    rl = get_policy().rate_limits
    assert rl.per_recipient.max_per_day > 0
    assert rl.per_recipient.max_per_week > 0
    assert rl.per_bu.max_per_day > 0
    assert rl.global_limits.max_per_hour > 0


def test_per_recipient_daily_limit_le_weekly() -> None:
    rl = get_policy().rate_limits.per_recipient
    assert rl.max_per_day <= rl.max_per_week, (
        "max_per_day must be <= max_per_week for per-recipient rate limits"
    )
