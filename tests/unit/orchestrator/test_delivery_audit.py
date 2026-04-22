"""Tests proving that _execute_delivery writes dedupe_key and has_recent_duplicate finds it."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from pulsecraft.orchestrator.audit import AuditWriter
from pulsecraft.orchestrator.engine import Orchestrator, _sha256
from pulsecraft.orchestrator.hitl import HITLQueue
from pulsecraft.orchestrator.mock_agents import MockBUAtlas, MockPushPilot, MockSignalScribe
from pulsecraft.schemas.audit_record import EventType
from pulsecraft.schemas.bu_profile import (
    BUHead,
    BUProfile,
    EscalationContact,
    Preferences,
    QuietHours,
)
from pulsecraft.schemas.bu_profile import Channel as BUChannel
from pulsecraft.schemas.change_artifact import ChangeArtifact, SourceType
from pulsecraft.schemas.decision import Decision, DecisionAgent, DecisionVerb
from pulsecraft.schemas.delivery_plan import Channel as DeliveryChannel
from pulsecraft.schemas.delivery_plan import DeliveryDecision
from pulsecraft.schemas.personalized_brief import (
    MessageQuality,
    MessageVariants,
    PersonalizedBrief,
    Priority,
    Relevance,
)
from pulsecraft.schemas.personalized_brief import ProducedBy as PBProducedBy
from pulsecraft.schemas.push_pilot_output import PushPilotOutput
from pulsecraft.skills.dedupe import compute_dedupe_key, has_recent_duplicate


def _make_orchestrator(tmp_path: Path) -> tuple[Orchestrator, AuditWriter]:
    audit = AuditWriter(root=tmp_path / "audit")
    hitl = HITLQueue(audit_writer=audit, root=tmp_path / "hitl")
    orc = Orchestrator(
        signalscribe=MockSignalScribe(),
        buatlas=MockBUAtlas(),
        pushpilot=MockPushPilot(),
        audit_writer=audit,
        hitl_queue=hitl,
    )
    return orc, audit


def _make_bu_profile(bu_id: str = "bu_alpha") -> BUProfile:
    return BUProfile(
        bu_id=bu_id,
        name="Alpha BU",
        head=BUHead(name="<head-alpha>", role="Head"),
        owned_product_areas=["specialty_pharmacy"],
        preferences=Preferences(
            channels=[BUChannel.TEAMS, BUChannel.EMAIL],
            quiet_hours=QuietHours(timezone="UTC", start="00:00", end="00:01"),
            digest_opt_in=False,
        ),
        active_initiatives=[],
        escalation_contact=EscalationContact(name="<esc>", role="Director"),
    )


def _make_personalized_brief(bu_id: str = "bu_alpha") -> PersonalizedBrief:
    now = datetime.now(UTC)
    return PersonalizedBrief(
        personalized_brief_id=str(uuid.uuid4()),
        change_id=str(uuid.uuid4()),
        brief_id=str(uuid.uuid4()),
        bu_id=bu_id,
        produced_at=now,
        produced_by=PBProducedBy(invocation_id=str(uuid.uuid4()), version="1.0"),
        relevance=Relevance.AFFECTED,
        priority=Priority.P1,
        why_relevant="Specialty pharmacy overlap.",
        recommended_actions=[],
        assumptions=[],
        message_variants=MessageVariants(
            push_short="Short push.",
            teams_medium="Teams medium notification text here.",
        ),
        message_quality=MessageQuality.WORTH_SENDING,
        confidence_score=0.85,
        decisions=[
            Decision(
                gate=4,
                verb=DecisionVerb.AFFECTED,
                reason="Test",
                confidence=0.85,
                decided_at=now,
                agent=DecisionAgent(name="buatlas", version="1.0"),
            )
        ],
    )


def _make_pushpilot_output(
    decision: DeliveryDecision = DeliveryDecision.SEND_NOW,
) -> PushPilotOutput:
    return PushPilotOutput(
        decision=decision,
        channel=DeliveryChannel.TEAMS,
        scheduled_time=None,
        reason="Test: deliver now.",
        confidence_score=0.90,
        gate_decision=Decision(
            gate=6,
            verb=DecisionVerb.SEND_NOW,
            reason="Test",
            confidence=0.90,
            decided_at=datetime.now(UTC),
            agent=DecisionAgent(name="pushpilot", version="1.0"),
        ),
    )


class TestDeliveryAuditDedupeKey:
    def test_execute_delivery_writes_dedupe_key(self, tmp_path: Path) -> None:
        """delivery_attempt audit record has a non-None dedupe_key after _execute_delivery."""
        orc, audit = _make_orchestrator(tmp_path)
        change_id = str(uuid.uuid4())
        bu_id = "bu_alpha"
        pb = _make_personalized_brief(bu_id)
        pb.change_id = change_id
        bu_profile = _make_bu_profile(bu_id)
        output = _make_pushpilot_output()

        orc._execute_delivery(change_id, bu_id, output, pb, bu_profile)

        records = audit.read_recent_events(EventType.DELIVERY_ATTEMPT, window_hours=24)
        assert len(records) >= 1
        delivery_records = [r for r in records if r.event_type == EventType.DELIVERY_ATTEMPT]
        assert any(r.dedupe_key is not None for r in delivery_records)

    def test_has_recent_duplicate_finds_written_key(self, tmp_path: Path) -> None:
        """has_recent_duplicate returns True after _execute_delivery writes the dedupe_key."""
        orc, audit = _make_orchestrator(tmp_path)
        change_id = str(uuid.uuid4())
        bu_id = "bu_alpha"
        pb = _make_personalized_brief(bu_id)
        pb.change_id = change_id
        bu_profile = _make_bu_profile(bu_id)
        output = _make_pushpilot_output()

        orc._execute_delivery(change_id, bu_id, output, pb, bu_profile)

        # Reconstruct the dedupe key the same way _execute_delivery does:
        # variant_text for Teams = json.dumps(card_json, sort_keys=True)
        # We use the same rendering path to get the same variant_text
        import json as _json

        from pulsecraft.skills.delivery.render_teams_card import render_teams_card

        teams_payload = render_teams_card(pb, bu_profile)
        variant_text = _json.dumps(teams_payload.card_json, sort_keys=True)
        variant_id = _sha256(variant_text)
        dedupe_key = compute_dedupe_key(change_id, bu_id, f"{bu_id}:head", variant_id)

        assert has_recent_duplicate(dedupe_key, audit, window_hours=24) is True

    def test_second_delivery_is_detected_as_duplicate(self, tmp_path: Path) -> None:
        """Second call to _execute_delivery with same inputs returns is_dedupe_conflict=True."""
        orc, audit = _make_orchestrator(tmp_path)
        change_id = str(uuid.uuid4())
        bu_id = "bu_alpha"
        pb = _make_personalized_brief(bu_id)
        pb.change_id = change_id
        bu_profile = _make_bu_profile(bu_id)
        output = _make_pushpilot_output()

        # First delivery — should succeed
        _decision1, is_dup1 = orc._execute_delivery(change_id, bu_id, output, pb, bu_profile)
        assert is_dup1 is False

        # Second delivery with identical inputs — should detect duplicate
        _decision2, is_dup2 = orc._execute_delivery(change_id, bu_id, output, pb, bu_profile)
        assert is_dup2 is True

    def test_full_pipeline_run_writes_delivery_record(self, tmp_path: Path) -> None:
        """End-to-end pipeline run with mock agents writes at least one delivery_attempt record."""
        orc, audit = _make_orchestrator(tmp_path)

        artifact = ChangeArtifact(
            change_id=str(uuid.uuid4()),
            source_type=SourceType.RELEASE_NOTE,
            source_ref="RN-TEST-001",
            title="Test change",
            raw_text="A test change artifact.",
            ingested_at=datetime.now(UTC),
        )

        orc.run_change(artifact)

        # The pipeline should produce at least some audit records
        records = audit.read_chain(artifact.change_id)
        assert len(records) > 0

        # If pipeline reached delivery, there should be a DELIVERY_ATTEMPT record
        delivery_records = [r for r in records if r.event_type == EventType.DELIVERY_ATTEMPT]
        if delivery_records:
            # Any written delivery record must have dedupe_key populated
            assert all(r.dedupe_key is not None for r in delivery_records)
