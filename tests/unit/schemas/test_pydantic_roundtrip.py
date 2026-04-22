"""Round-trip tests: build minimal valid instance → serialize → validate JSON schema → parse back → equal."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from referencing import Registry

from pulsecraft.schemas import (
    AuditDecision,
    AuditMetrics,
    AuditOutcome,
    AuditRecord,
    BUProfile,
    ChangeArtifact,
    ChangeBrief,
    ChangeType,
    Channel,
    DecisionVerb,
    DeliveryDecision,
    DeliveryPlan,
    EventType,
    MessageQuality,
    MessageVariants,
    PersonalizedBrief,
    PolicyCheck,
    Priority,
    QuietHours,
    Relevance,
    RetryCondition,
    RetryPolicy,
    SourceCitation,
    SourceType,
    Timeline,
    TimelineStatus,
)
from pulsecraft.schemas.audit_record import Actor, ActorType
from pulsecraft.schemas.bu_profile import BUHead, EscalationContact, Preferences
from pulsecraft.schemas.change_brief import ProducedBy as BriefProducedBy
from pulsecraft.schemas.decision import Decision, DecisionAgent
from pulsecraft.schemas.delivery_plan import (
    BackoffStrategy,
    RecipientDisplay,
)
from pulsecraft.schemas.delivery_plan import (
    ProducedBy as DeliveryProducedBy,
)
from pulsecraft.schemas.personalized_brief import (
    ProducedBy as PersonalizedProducedBy,
)
from pulsecraft.schemas.personalized_brief import (
    RecommendedAction,
)
from tests.unit.schemas.conftest import SCHEMA_FILES, make_validator

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures" / "schemas" / "minimal_valid"

NOW = datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC)
UUID_A = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
UUID_B = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
UUID_C = "c3d4e5f6-a7b8-9012-cdef-123456789012"
UUID_D = "d4e5f6a7-b8c9-0123-defa-234567890123"
UUID_E = "e5f6a7b8-c9d0-1234-efab-345678901234"
UUID_F = "f6a7b8c9-d0e1-2345-fabc-456789012345"
SHA256 = "a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2"

_DECISION_GATE1 = Decision(
    gate=1,
    verb=DecisionVerb.COMMUNICATE,
    reason="Workflow change visible to specialty pharmacy stakeholders.",
    confidence=0.9,
    decided_at=NOW,
    agent=DecisionAgent(name="signalscribe", version="0.1.0"),
)


def _validate(instance_dict: dict, schema_name: str, registry: Registry) -> None:
    schema = json.loads(SCHEMA_FILES[schema_name].read_text())
    validator = make_validator(schema, registry)
    validator.validate(instance_dict)


def test_change_artifact_roundtrip(schema_registry: Registry) -> None:
    model = ChangeArtifact(
        change_id=UUID_A,
        source_type=SourceType.RELEASE_NOTE,
        source_ref="RN-2026-042",
        ingested_at=NOW,
        title="Order submission workflow updated",
        raw_text="Updated two-pass verification. No PII.",
    )
    serialized = json.loads(model.model_dump_json())
    _validate(serialized, "change_artifact", schema_registry)
    parsed = ChangeArtifact.model_validate(serialized)
    assert parsed == model


def test_change_artifact_fixture_validates(schema_registry: Registry) -> None:
    data = json.loads((FIXTURES_DIR / "change_artifact.json").read_text())
    schema = json.loads(SCHEMA_FILES["change_artifact"].read_text())
    make_validator(schema, schema_registry).validate(data)


def test_change_brief_roundtrip(schema_registry: Registry) -> None:
    model = ChangeBrief(
        brief_id=UUID_B,
        change_id=UUID_A,
        produced_at=NOW,
        produced_by=BriefProducedBy(version="0.1.0"),
        summary="Two-pass verification added for specialty pharmacy orders.",
        before="Single-pass validation.",
        after="Two-pass verification step.",
        change_type=ChangeType.BEHAVIOR_CHANGE,
        impact_areas=["specialty_pharmacy"],
        affected_segments=["internal_users"],
        timeline=Timeline(status=TimelineStatus.RIPE),
        required_actions=[],
        risks=[],
        mitigations=[],
        faq=[],
        sources=[
            SourceCitation(
                type=SourceType.RELEASE_NOTE, ref="RN-2026-042", quote="updated verification step"
            )
        ],
        confidence_score=0.87,
        decisions=[_DECISION_GATE1],
    )
    serialized = json.loads(model.model_dump_json())
    _validate(serialized, "change_brief", schema_registry)
    parsed = ChangeBrief.model_validate(serialized)
    assert parsed == model


def test_change_brief_fixture_validates(schema_registry: Registry) -> None:
    data = json.loads((FIXTURES_DIR / "change_brief.json").read_text())
    schema = json.loads(SCHEMA_FILES["change_brief"].read_text())
    make_validator(schema, schema_registry).validate(data)


def test_personalized_brief_roundtrip(schema_registry: Registry) -> None:
    model = PersonalizedBrief(
        personalized_brief_id=UUID_C,
        change_id=UUID_A,
        brief_id=UUID_B,
        bu_id="bu-alpha",
        produced_at=NOW,
        produced_by=PersonalizedProducedBy(version="0.1.0", invocation_id=UUID_D),
        relevance=Relevance.AFFECTED,
        priority=Priority.P1,
        why_relevant="Bu-alpha owns specialty pharmacy; field teams need preparation.",
        recommended_actions=[RecommendedAction(owner="BU head", action="Assign training update")],
        assumptions=["Bu-alpha field teams use the affected workflow."],
        message_variants=MessageVariants(push_short="Specialty pharmacy order flow updated."),
        message_quality=MessageQuality.WORTH_SENDING,
        confidence_score=0.83,
        decisions=[
            Decision(
                gate=4,
                verb=DecisionVerb.AFFECTED,
                reason="Owns product area.",
                confidence=0.85,
                decided_at=NOW,
                agent=DecisionAgent(name="buatlas", version="0.1.0"),
            ),
            Decision(
                gate=5,
                verb=DecisionVerb.WORTH_SENDING,
                reason="Specific consequence named.",
                confidence=0.83,
                decided_at=NOW,
                agent=DecisionAgent(name="buatlas", version="0.1.0"),
            ),
        ],
    )
    serialized = json.loads(model.model_dump_json())
    _validate(serialized, "personalized_brief", schema_registry)
    parsed = PersonalizedBrief.model_validate(serialized)
    assert parsed == model


def test_personalized_brief_fixture_validates(schema_registry: Registry) -> None:
    data = json.loads((FIXTURES_DIR / "personalized_brief.json").read_text())
    schema = json.loads(SCHEMA_FILES["personalized_brief"].read_text())
    make_validator(schema, schema_registry).validate(data)


def test_delivery_plan_roundtrip(schema_registry: Registry) -> None:
    model = DeliveryPlan(
        delivery_id=UUID_E,
        personalized_brief_id=UUID_C,
        change_id=UUID_A,
        bu_id="bu-alpha",
        recipient_id="recipient-opaque-001",
        recipient_display=RecipientDisplay(name="<display-name>", role="BU Head"),
        produced_at=NOW,
        produced_by=DeliveryProducedBy(version="0.1.0"),
        decision=DeliveryDecision.SEND_NOW,
        channel=Channel.TEAMS,
        scheduled_time=None,
        reason="P1 notification within working hours, no policy conflicts.",
        dedupe_key=SHA256,
        policy_check=PolicyCheck(passed=True),
        retry_policy=RetryPolicy(
            max_attempts=3,
            backoff=BackoffStrategy.EXPONENTIAL,
            retry_on=[RetryCondition.TRANSIENT_ERROR],
        ),
        confidence_score=0.91,
        decisions=[
            Decision(
                gate=6,
                verb=DecisionVerb.SEND_NOW,
                reason="P1 priority, no conflicts.",
                confidence=0.91,
                decided_at=NOW,
                agent=DecisionAgent(name="pushpilot", version="0.1.0"),
            ),
        ],
    )
    serialized = json.loads(model.model_dump_json())
    _validate(serialized, "delivery_plan", schema_registry)
    parsed = DeliveryPlan.model_validate(serialized)
    assert parsed == model


def test_delivery_plan_fixture_validates(schema_registry: Registry) -> None:
    data = json.loads((FIXTURES_DIR / "delivery_plan.json").read_text())
    schema = json.loads(SCHEMA_FILES["delivery_plan"].read_text())
    make_validator(schema, schema_registry).validate(data)


def test_bu_profile_roundtrip(schema_registry: Registry) -> None:
    model = BUProfile(
        bu_id="bu-alpha",
        name="Alpha Business Unit",
        head=BUHead(name="<display-name>", role="VP General Manager"),
        owned_product_areas=["specialty_pharmacy"],
        preferences=Preferences(
            channels=[Channel.TEAMS],
            quiet_hours=QuietHours(timezone="America/Chicago", start="18:00", end="08:00"),
            digest_opt_in=True,
        ),
        active_initiatives=["Specialty pharmacy access initiative"],
        escalation_contact=EscalationContact(name="<display-name>", role="Chief of Staff"),
    )
    serialized = json.loads(model.model_dump_json())
    _validate(serialized, "bu_profile", schema_registry)
    parsed = BUProfile.model_validate(serialized)
    assert parsed == model


def test_bu_profile_fixture_validates(schema_registry: Registry) -> None:
    data = json.loads((FIXTURES_DIR / "bu_profile.json").read_text())
    schema = json.loads(SCHEMA_FILES["bu_profile"].read_text())
    make_validator(schema, schema_registry).validate(data)


def test_audit_record_roundtrip(schema_registry: Registry) -> None:
    model = AuditRecord(
        audit_id=UUID_F,
        timestamp=NOW,
        event_type=EventType.AGENT_INVOCATION,
        change_id=UUID_A,
        actor=Actor(type=ActorType.AGENT, id="signalscribe", version="0.1.0"),
        action="completed",
        input_hash=SHA256,
        output_summary="gate=1 verb=COMMUNICATE confidence=0.90",
        decision=AuditDecision(
            gate=1, verb="COMMUNICATE", reason="Workflow change visible to stakeholders."
        ),
        metrics=AuditMetrics(token_count_input=1200, token_count_output=850, latency_ms=3200),
        outcome=AuditOutcome.SUCCESS,
    )
    serialized = json.loads(model.model_dump_json())
    _validate(serialized, "audit_record", schema_registry)
    parsed = AuditRecord.model_validate(serialized)
    assert parsed == model


def test_audit_record_fixture_validates(schema_registry: Registry) -> None:
    data = json.loads((FIXTURES_DIR / "audit_record.json").read_text())
    schema = json.loads(SCHEMA_FILES["audit_record"].read_text())
    make_validator(schema, schema_registry).validate(data)
