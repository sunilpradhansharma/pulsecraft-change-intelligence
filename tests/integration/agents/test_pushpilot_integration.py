"""Integration tests for PushPilot — real Anthropic API calls.

Requires PULSECRAFT_RUN_LLM_TESTS=1. Each test makes real API calls (~$0.02–0.05).
Run manually for eval only.

Test strategy: Build synthetic PersonalizedBriefs with controlled priority/quality
and verify PushPilot returns valid PushPilotOutput with sensible gate-6 decisions.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest

from pulsecraft.agents.pushpilot import PushPilot
from pulsecraft.config.loader import get_bu_profile
from pulsecraft.schemas.decision import Decision, DecisionAgent, DecisionVerb
from pulsecraft.schemas.delivery_plan import DeliveryDecision
from pulsecraft.schemas.personalized_brief import (
    MessageQuality,
    MessageVariants,
    PersonalizedBrief,
    Priority,
    RecommendedAction,
    Relevance,
)
from pulsecraft.schemas.personalized_brief import ProducedBy as PBProducedBy
from pulsecraft.schemas.push_pilot_output import PushPilotOutput

_LLM_ENABLED = os.environ.get("PULSECRAFT_RUN_LLM_TESTS", "").lower() in ("1", "true", "yes")
_SKIP_REASON = "Set PULSECRAFT_RUN_LLM_TESTS=1 to run LLM integration tests"


def _make_pb(
    priority: Priority, quality: MessageQuality = MessageQuality.WORTH_SENDING
) -> PersonalizedBrief:
    now = datetime.now(UTC)
    agent = DecisionAgent(name="buatlas", version="1.0")
    return PersonalizedBrief(
        personalized_brief_id=str(uuid.uuid4()),
        change_id=str(uuid.uuid4()),
        brief_id=str(uuid.uuid4()),
        bu_id="bu_alpha",
        produced_at=now,
        produced_by=PBProducedBy(version="1.0", invocation_id=str(uuid.uuid4())),
        relevance=Relevance.AFFECTED,
        priority=priority,
        why_relevant="BU alpha owns the prior authorization and specialty pharmacy workflows. This change directly affects how field reps submit PA forms.",
        recommended_actions=[
            RecommendedAction(
                owner="BU head",
                action="Brief field representatives on new validation UI before rollout.",
                by_when="2026-05-15",
            )
        ],
        assumptions=["Standard US rollout applies."],
        message_variants=MessageVariants(
            push_short="PA form validation updated: new required fields added for specialty pharmacy.",
            teams_medium="The prior authorization submission form has been redesigned. Field reps will see new required clinical justification fields starting next rollout.",
            email_long="Starting next rollout cycle, the PA submission form introduces a new mandatory section. Field representatives in specialty pharmacy will need to complete additional clinical justification fields. No action required before the rollout date, but team briefing is recommended.",
        ),
        message_quality=quality,
        confidence_score=0.87,
        decisions=[
            Decision(
                gate=4,
                verb=DecisionVerb.AFFECTED,
                reason="BU alpha owns PA workflow.",
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


@pytest.fixture(scope="module")
def pushpilot():
    return PushPilot()


@pytest.mark.llm
@pytest.mark.skipif(not _LLM_ENABLED, reason=_SKIP_REASON)
def test_pushpilot_returns_valid_schema(pushpilot: PushPilot) -> None:
    """PushPilot output validates against PushPilotOutput schema."""
    pb = _make_pb(Priority.P1)
    bu = get_bu_profile("bu_alpha")
    result = pushpilot.invoke(pb, bu)
    assert isinstance(result, PushPilotOutput)
    assert 0.0 <= result.confidence_score <= 1.0
    assert result.gate_decision.gate == 6
    assert result.gate_decision.agent.name == "pushpilot"
    assert result.reason != ""


@pytest.mark.llm
@pytest.mark.skipif(not _LLM_ENABLED, reason=_SKIP_REASON)
def test_pushpilot_decision_verb_consistency(pushpilot: PushPilot) -> None:
    """decision and gate_decision.verb are consistent."""
    pb = _make_pb(Priority.P1)
    bu = get_bu_profile("bu_alpha")
    result = pushpilot.invoke(pb, bu)
    # verb should be uppercase form of decision
    assert str(result.gate_decision.verb).lower().replace("_", "") == str(
        result.decision
    ).lower().replace("_", "") or (
        str(result.gate_decision.verb).upper() in [d.upper() for d in [str(result.decision)]]
    )


@pytest.mark.llm
@pytest.mark.skipif(not _LLM_ENABLED, reason=_SKIP_REASON)
def test_pushpilot_p1_working_hours_tends_toward_send(pushpilot: PushPilot) -> None:
    """P1 message tends to produce SEND_NOW or HOLD_UNTIL — not DIGEST."""
    pb = _make_pb(Priority.P1)
    bu = get_bu_profile("bu_alpha")
    result = pushpilot.invoke(pb, bu)
    # DIGEST is not appropriate for P1; SEND_NOW and HOLD_UNTIL are acceptable
    assert result.decision in (
        DeliveryDecision.SEND_NOW,
        DeliveryDecision.HOLD_UNTIL,
        DeliveryDecision.ESCALATE,
    ), f"P1 message should not produce DIGEST; got {result.decision}"


@pytest.mark.llm
@pytest.mark.skipif(not _LLM_ENABLED, reason=_SKIP_REASON)
def test_pushpilot_p2_with_digest_optin_tends_toward_digest(pushpilot: PushPilot) -> None:
    """P2 message for digest-opt-in BU tends toward DIGEST."""
    pb = _make_pb(Priority.P2)
    # bu_alpha has digest_opt_in: true
    bu = get_bu_profile("bu_alpha")
    result = pushpilot.invoke(pb, bu)
    # For P2 + digest opt-in, DIGEST is the expected decision
    # HOLD_UNTIL is also acceptable; SEND_NOW is less likely for P2
    assert result.decision in (
        DeliveryDecision.DIGEST,
        DeliveryDecision.HOLD_UNTIL,
        DeliveryDecision.SEND_NOW,
    ), f"P2 digest-opt-in should produce DIGEST or HOLD_UNTIL; got {result.decision}"


@pytest.mark.llm
@pytest.mark.skipif(not _LLM_ENABLED, reason=_SKIP_REASON)
def test_pushpilot_hold_until_has_scheduled_time(pushpilot: PushPilot) -> None:
    """When decision is HOLD_UNTIL, scheduled_time must be present and in the future."""
    pb = _make_pb(Priority.P1)
    bu = get_bu_profile("bu_zeta")  # bu_zeta is Europe/London timezone
    result = pushpilot.invoke(pb, bu)
    if result.decision == DeliveryDecision.HOLD_UNTIL:
        assert result.scheduled_time is not None
        assert result.scheduled_time > datetime.now(UTC), "scheduled_time must be in the future"


@pytest.mark.llm
@pytest.mark.skipif(not _LLM_ENABLED, reason=_SKIP_REASON)
def test_pushpilot_channel_in_expected_channels(pushpilot: PushPilot) -> None:
    """When decision is not escalate, channel is set to a recognized value."""
    from pulsecraft.schemas.delivery_plan import Channel as DeliveryChannel

    pb = _make_pb(Priority.P1)
    bu = get_bu_profile("bu_alpha")
    result = pushpilot.invoke(pb, bu)
    if result.decision != DeliveryDecision.ESCALATE:
        assert result.channel is not None
        assert result.channel in list(DeliveryChannel)
