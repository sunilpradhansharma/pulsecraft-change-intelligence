"""Unit tests for render_portal_digest skill."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

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
from pulsecraft.skills.delivery.render_portal_digest import render_portal_digest


def _bu_profile() -> BUProfile:
    return BUProfile(
        bu_id="bu_alpha",
        name="Alpha BU",
        head=BUHead(name="<head-alpha>", role="Head"),
        owned_product_areas=["specialty_pharmacy"],
        preferences=Preferences(
            channels=[BUChannel.EMAIL],
            quiet_hours=QuietHours(timezone="UTC", start="20:00", end="08:00"),
            digest_opt_in=True,
        ),
        active_initiatives=[],
        escalation_contact=EscalationContact(name="<esc>", role="Director"),
    )


def _brief(why_relevant: str = "Relevant impact.") -> PersonalizedBrief:
    now = datetime.now(UTC)
    return PersonalizedBrief(
        personalized_brief_id=str(uuid.uuid4()),
        change_id=str(uuid.uuid4()),
        brief_id=str(uuid.uuid4()),
        bu_id="bu_alpha",
        produced_at=now,
        produced_by=PBProducedBy(invocation_id=str(uuid.uuid4()), version="1.0"),
        relevance=Relevance.AFFECTED,
        priority=Priority.P2,
        why_relevant=why_relevant,
        recommended_actions=[],
        assumptions=[],
        message_variants=MessageVariants(push_short="Short text."),
        message_quality=MessageQuality.WORTH_SENDING,
        confidence_score=0.80,
        decisions=[
            Decision(
                gate=4,
                verb=DecisionVerb.AFFECTED,
                reason="Mock",
                confidence=0.80,
                decided_at=now,
                agent=DecisionAgent(name="buatlas", version="1.0"),
            )
        ],
    )


class TestRenderPortalDigest:
    def test_happy_path_with_single_brief(self) -> None:
        payload = render_portal_digest([_brief()], _bu_profile())
        assert payload.item_count == 1
        assert payload.bu_id == "bu_alpha"
        assert payload.markdown

    def test_item_count_matches_input(self) -> None:
        payload = render_portal_digest([_brief(), _brief()], _bu_profile())
        assert payload.item_count == 2

    def test_empty_list_returns_zero_items(self) -> None:
        payload = render_portal_digest([], _bu_profile())
        assert payload.item_count == 0

    def test_markdown_contains_bu_name(self) -> None:
        payload = render_portal_digest([_brief()], _bu_profile())
        assert "Alpha BU" in payload.markdown

    def test_digest_date_matches_provided_date(self) -> None:
        fixed = datetime(2026, 4, 22, 9, 0, tzinfo=UTC)
        payload = render_portal_digest([_brief()], _bu_profile(), digest_date=fixed)
        assert payload.digest_date.isoformat() == "2026-04-22"
