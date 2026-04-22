"""Unit tests for render_push skill."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from pulsecraft.schemas.bu_profile import (
    BUHead,
    BUProfile,
    EscalationContact,
    Preferences,
    QuietHours,
)
from pulsecraft.schemas.bu_profile import Channel as BUChannel
from pulsecraft.schemas.decision import Decision, DecisionAgent, DecisionVerb
from pulsecraft.schemas.personalized_brief import (
    MessageQuality,
    MessageVariants,
    PersonalizedBrief,
    Priority,
    Relevance,
)
from pulsecraft.schemas.personalized_brief import ProducedBy as PBProducedBy
from pulsecraft.skills.delivery.common import RenderingError
from pulsecraft.skills.delivery.render_push import render_push


def _bu_profile() -> BUProfile:
    return BUProfile(
        bu_id="bu_alpha",
        name="Alpha BU",
        head=BUHead(name="<head-alpha>", role="Head of Alpha BU"),
        owned_product_areas=["specialty_pharmacy"],
        preferences=Preferences(
            channels=[BUChannel.PUSH, BUChannel.EMAIL],
            quiet_hours=QuietHours(timezone="UTC", start="20:00", end="08:00"),
            digest_opt_in=False,
        ),
        active_initiatives=["initiative one"],
        escalation_contact=EscalationContact(name="<esc-alpha>", role="Director"),
    )


def _brief(push_short: str | None = "Short push notification text.") -> PersonalizedBrief:
    now = datetime.now(UTC)
    return PersonalizedBrief(
        personalized_brief_id=str(uuid.uuid4()),
        change_id=str(uuid.uuid4()),
        brief_id=str(uuid.uuid4()),
        bu_id="bu_alpha",
        produced_at=now,
        produced_by=PBProducedBy(invocation_id=str(uuid.uuid4()), version="1.0"),
        relevance=Relevance.AFFECTED,
        priority=Priority.P1,
        why_relevant="Relevant.",
        recommended_actions=[],
        assumptions=[],
        message_variants=MessageVariants(push_short=push_short),
        message_quality=MessageQuality.WORTH_SENDING,
        confidence_score=0.85,
        decisions=[
            Decision(
                gate=4,
                verb=DecisionVerb.AFFECTED,
                reason="Mock",
                confidence=0.85,
                decided_at=now,
                agent=DecisionAgent(name="buatlas", version="1.0"),
            )
        ],
    )


class TestRenderPush:
    def test_happy_path_returns_payload(self) -> None:
        payload = render_push(_brief(), _bu_profile())
        assert payload.title
        assert payload.body

    def test_body_contains_push_short_text(self) -> None:
        payload = render_push(_brief(push_short="Specific push content."), _bu_profile())
        assert "Specific push content." in payload.body

    def test_title_within_65_chars(self) -> None:
        payload = render_push(_brief(), _bu_profile())
        assert len(payload.title) <= 65

    def test_long_title_is_truncated(self) -> None:
        long_bu = BUProfile(
            bu_id="bu_alpha",
            name="A" * 100,
            head=BUHead(name="<head>", role="Head"),
            owned_product_areas=["x"],
            preferences=Preferences(
                channels=[BUChannel.PUSH],
                quiet_hours=QuietHours(timezone="UTC", start="20:00", end="08:00"),
                digest_opt_in=False,
            ),
            active_initiatives=[],
            escalation_contact=EscalationContact(name="<esc>", role="Director"),
        )
        payload = render_push(_brief(), long_bu)
        assert len(payload.title) <= 65

    def test_missing_variants_raises(self) -> None:
        brief = _brief()
        brief.message_variants = None
        with pytest.raises(RenderingError):
            render_push(brief, _bu_profile())

    def test_no_push_short_raises(self) -> None:
        brief = _brief(push_short=None)
        with pytest.raises(RenderingError):
            render_push(brief, _bu_profile())
