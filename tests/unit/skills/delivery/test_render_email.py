"""Unit tests for render_email skill."""

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
from pulsecraft.skills.delivery.render_email import render_email


def _bu_profile(bu_id: str = "bu_alpha") -> BUProfile:
    return BUProfile(
        bu_id=bu_id,
        name="Alpha BU",
        head=BUHead(name="<head-alpha>", role="Head of Alpha BU"),
        owned_product_areas=["specialty_pharmacy"],
        preferences=Preferences(
            channels=[BUChannel.EMAIL, BUChannel.TEAMS],
            quiet_hours=QuietHours(timezone="UTC", start="20:00", end="08:00"),
            digest_opt_in=False,
        ),
        active_initiatives=["initiative one"],
        escalation_contact=EscalationContact(name="<esc-alpha>", role="Director"),
    )


def _brief(
    email_long: str | None = "Long email body with detailed information.",
    teams_medium: str | None = None,
    push_short: str | None = "Short push.",
) -> PersonalizedBrief:
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
        why_relevant="Relevant because of specialty pharmacy overlap.",
        recommended_actions=[],
        assumptions=[],
        message_variants=MessageVariants(
            push_short=push_short, teams_medium=teams_medium, email_long=email_long
        ),
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


class TestRenderEmail:
    def test_happy_path_returns_all_parts(self) -> None:
        payload = render_email(_brief(), _bu_profile())
        assert payload.subject
        assert payload.body_text
        assert payload.body_html

    def test_subject_includes_bu_name(self) -> None:
        payload = render_email(_brief(), _bu_profile())
        assert "Alpha BU" in payload.subject

    def test_body_text_contains_email_long_content(self) -> None:
        payload = render_email(_brief(email_long="Very specific detail here."), _bu_profile())
        assert "Very specific detail here." in payload.body_text

    def test_body_html_is_valid_html(self) -> None:
        payload = render_email(_brief(), _bu_profile())
        assert "<html" in payload.body_html
        assert "</html>" in payload.body_html

    def test_missing_variants_raises(self) -> None:
        brief = _brief()
        brief.message_variants = None
        with pytest.raises(RenderingError):
            render_email(brief, _bu_profile())

    def test_falls_back_to_push_short_when_no_email_long(self) -> None:
        payload = render_email(
            _brief(email_long=None, teams_medium=None, push_short="Only push text."),
            _bu_profile(),
        )
        assert "Only push text." in payload.body_text
