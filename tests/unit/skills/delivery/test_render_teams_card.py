"""Unit tests for render_teams_card skill."""

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
from pulsecraft.skills.delivery.render_teams_card import render_teams_card


def _bu_profile(bu_id: str = "bu_alpha") -> BUProfile:
    return BUProfile(
        bu_id=bu_id,
        name="Alpha BU",
        head=BUHead(name="<head-alpha>", role="Head of Alpha BU"),
        owned_product_areas=["specialty_pharmacy"],
        preferences=Preferences(
            channels=[BUChannel.TEAMS, BUChannel.EMAIL],
            quiet_hours=QuietHours(timezone="UTC", start="20:00", end="08:00"),
            digest_opt_in=False,
        ),
        active_initiatives=["initiative one"],
        escalation_contact=EscalationContact(name="<esc-alpha>", role="Director"),
    )


def _brief(
    bu_id: str = "bu_alpha",
    teams_medium: str | None = "Teams medium notification text.",
    push_short: str | None = "Short push text.",
    message_variants: MessageVariants | None = None,
) -> PersonalizedBrief:
    now = datetime.now(UTC)
    variants = message_variants or MessageVariants(
        push_short=push_short,
        teams_medium=teams_medium,
    )
    return PersonalizedBrief(
        personalized_brief_id=str(uuid.uuid4()),
        change_id=str(uuid.uuid4()),
        brief_id=str(uuid.uuid4()),
        bu_id=bu_id,
        produced_at=now,
        produced_by=PBProducedBy(invocation_id=str(uuid.uuid4()), version="1.0"),
        relevance=Relevance.AFFECTED,
        priority=Priority.P1,
        why_relevant="This affects specialty pharmacy workflows.",
        recommended_actions=[],
        assumptions=[],
        message_variants=variants,
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


class TestRenderTeamsCard:
    def test_happy_path_returns_valid_payload(self) -> None:
        payload = render_teams_card(_brief(), _bu_profile())
        assert isinstance(payload.card_json, dict)
        assert payload.card_json["type"] == "AdaptiveCard"
        assert payload.length_bytes > 0

    def test_uses_teams_medium_body(self) -> None:
        payload = render_teams_card(_brief(teams_medium="Teams body here."), _bu_profile())
        rendered = str(payload.card_json)
        assert "Teams body here." in rendered

    def test_falls_back_to_push_short_when_no_teams_medium(self) -> None:
        payload = render_teams_card(
            _brief(teams_medium=None, push_short="Fallback push text."), _bu_profile()
        )
        assert "Fallback push text." in str(payload.card_json)

    def test_missing_message_variants_raises(self) -> None:
        brief = _brief()
        brief.message_variants = None
        with pytest.raises(RenderingError):
            render_teams_card(brief, _bu_profile())

    def test_no_teams_medium_and_no_push_short_raises(self) -> None:
        brief = _brief(teams_medium=None, push_short=None)
        with pytest.raises(RenderingError):
            render_teams_card(brief, _bu_profile())

    def test_card_contains_bu_name(self) -> None:
        payload = render_teams_card(_brief(), _bu_profile())
        assert "Alpha BU" in str(payload.card_json)
