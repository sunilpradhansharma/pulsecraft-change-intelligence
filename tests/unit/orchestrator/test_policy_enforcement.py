"""Unit tests for PushPilot policy enforcement in the orchestrator.

Verifies that code-level invariants (quiet hours, channel approval, confidence)
are correctly applied after PushPilot returns. Tests the agent-vs-code split:
agent expresses preference; orchestrator enforces policy.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from pulsecraft.config.loader import get_bu_profile
from pulsecraft.orchestrator.audit import AuditWriter
from pulsecraft.orchestrator.engine import Orchestrator
from pulsecraft.orchestrator.hitl import HITLQueue
from pulsecraft.orchestrator.mock_agents import MockBUAtlas, MockPushPilot, MockSignalScribe
from pulsecraft.schemas.bu_profile import BUProfile, Preferences, QuietHours
from pulsecraft.schemas.decision import Decision, DecisionAgent, DecisionVerb
from pulsecraft.schemas.delivery_plan import Channel as DeliveryChannel
from pulsecraft.schemas.delivery_plan import DeliveryDecision
from pulsecraft.schemas.push_pilot_output import PushPilotOutput

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_orchestrator(tmp_path: Path, pushpilot=None):
    audit_writer = AuditWriter(root=tmp_path / "audit")
    hitl_queue = HITLQueue(audit_writer=audit_writer, root=tmp_path / "hitl")
    return Orchestrator(
        signalscribe=MockSignalScribe(),
        buatlas=MockBUAtlas(),
        pushpilot=pushpilot or MockPushPilot(),
        audit_writer=audit_writer,
        hitl_queue=hitl_queue,
    )


def _make_pushpilot_output(decision: str = "send_now") -> PushPilotOutput:
    now = datetime.now(UTC)
    scheduled = (now + timedelta(hours=10)).isoformat() if decision == "hold_until" else None
    return PushPilotOutput(
        decision=DeliveryDecision(decision),
        channel=DeliveryChannel.TEAMS if decision != "escalate" else None,
        scheduled_time=datetime.fromisoformat(scheduled) if scheduled else None,
        reason="Test: send now.",
        confidence_score=0.88,
        gate_decision=Decision(
            gate=6,
            verb=DecisionVerb.SEND_NOW if decision == "send_now" else DecisionVerb.HOLD_UNTIL,
            reason="Test.",
            confidence=0.88,
            decided_at=now,
            agent=DecisionAgent(name="pushpilot", version="1.0"),
        ),
    )


def _bu_profile_with_quiet_hours(
    timezone: str, start: str, end: str, channels: list[str] | None = None
) -> BUProfile:
    """Build a BUProfile with specified quiet hours."""
    from pulsecraft.schemas.bu_profile import BUHead, EscalationContact

    return BUProfile(
        bu_id="bu_test",
        name="Test BU",
        head=BUHead(name="<test-head>", role="Head of Test BU"),
        owned_product_areas=["test_area"],
        preferences=Preferences(
            channels=[DeliveryChannel(c) for c in (channels or ["teams", "email"])],
            quiet_hours=QuietHours(timezone=timezone, start=start, end=end),
            digest_opt_in=False,
            max_notifications_per_week=10,
        ),
        active_initiatives=["test initiative"],
        escalation_contact=EscalationContact(name="<test-escalation>", role="Test Director"),
    )


# ── Quiet hours enforcement ───────────────────────────────────────────────────


class TestQuietHoursDetection:
    """Test the _is_in_quiet_hours static helper."""

    def test_not_in_quiet_hours_returns_false(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        # Quiet hours 19:00-07:00 Chicago; test at 14:00 UTC (09:00 Chicago = outside quiet)
        bu = _bu_profile_with_quiet_hours("America/Chicago", "19:00", "07:00")
        test_time = datetime(2026, 4, 22, 14, 0, 0, tzinfo=UTC)  # 09:00 Chicago
        in_quiet, _ = orch._is_in_quiet_hours(bu, test_time)
        assert not in_quiet

    def test_in_quiet_hours_returns_true(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        # Quiet hours 19:00-07:00 Chicago; test at 02:00 UTC (21:00 prev day Chicago = quiet)
        bu = _bu_profile_with_quiet_hours("America/Chicago", "19:00", "07:00")
        test_time = datetime(2026, 4, 23, 2, 0, 0, tzinfo=UTC)  # 21:00 Chicago
        in_quiet, quiet_end = orch._is_in_quiet_hours(bu, test_time)
        assert in_quiet
        assert quiet_end is not None
        # End of quiet is 07:00 Chicago = 12:00 UTC on the 23rd
        assert quiet_end.hour == 12
        assert quiet_end.tzinfo is UTC

    def test_end_of_quiet_hours_is_utc(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        bu = _bu_profile_with_quiet_hours("America/New_York", "20:00", "08:00")
        test_time = datetime(2026, 4, 23, 2, 0, 0, tzinfo=UTC)  # 22:00 NY
        in_quiet, quiet_end = orch._is_in_quiet_hours(bu, test_time)
        assert in_quiet
        assert quiet_end is not None
        assert quiet_end.tzinfo is UTC

    def test_unknown_timezone_skips_quiet_hours(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        bu = _bu_profile_with_quiet_hours("Invalid/TimeZone", "19:00", "07:00")
        test_time = datetime(2026, 4, 23, 2, 0, 0, tzinfo=UTC)
        in_quiet, quiet_end = orch._is_in_quiet_hours(bu, test_time)
        assert not in_quiet
        assert quiet_end is None


class TestPolicyEnforcementQuietHours:
    """Test that SEND_NOW is downgraded to HOLD_UNTIL during quiet hours."""

    def test_send_now_in_quiet_hours_becomes_hold_until(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        bu = _bu_profile_with_quiet_hours("America/Chicago", "19:00", "07:00")
        # Simulate current time deep in quiet hours
        with MagicMock() as _:
            from unittest.mock import patch

            # Patch datetime.now(UTC) in engine to return a quiet-hours time
            with patch("pulsecraft.orchestrator.engine.datetime") as mock_dt:
                mock_dt.now.return_value = datetime(2026, 4, 23, 2, 0, 0, tzinfo=UTC)
                mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

                output = _make_pushpilot_output("send_now")
                from pulsecraft.config.loader import get_policy

                result = orch._enforce_pushpilot_policy(
                    str(uuid.uuid4()), "bu_test", output, bu, get_policy()
                )

        assert result.decision == DeliveryDecision.HOLD_UNTIL
        assert result.scheduled_time is not None
        assert (
            "POLICY OVERRIDE" in result.reason
            or "quiet_hours" in result.reason.lower()
            or "Policy override" in result.reason
        )

    def test_hold_until_not_further_modified_by_quiet_hours(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        bu = _bu_profile_with_quiet_hours("America/Chicago", "19:00", "07:00")
        output = _make_pushpilot_output("hold_until")
        from pulsecraft.config.loader import get_policy

        result = orch._enforce_pushpilot_policy(
            str(uuid.uuid4()), "bu_test", output, bu, get_policy()
        )
        # HOLD_UNTIL is preserved as-is (not further modified)
        assert result.decision == DeliveryDecision.HOLD_UNTIL

    def test_send_now_outside_quiet_hours_not_modified(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        bu = _bu_profile_with_quiet_hours("America/Chicago", "19:00", "07:00")
        output = _make_pushpilot_output("send_now")
        from pulsecraft.config.loader import get_policy

        with MagicMock():
            from unittest.mock import patch

            # Patch to working hours in Chicago
            with patch("pulsecraft.orchestrator.engine.datetime") as mock_dt:
                mock_dt.now.return_value = datetime(2026, 4, 22, 14, 0, 0, tzinfo=UTC)
                mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
                result = orch._enforce_pushpilot_policy(
                    str(uuid.uuid4()), "bu_test", output, bu, get_policy()
                )

        assert result.decision == DeliveryDecision.SEND_NOW


# ── Channel approval enforcement ──────────────────────────────────────────────


class TestPolicyEnforcementChannel:
    """Test that agent's channel preference is validated and overridden if not approved."""

    def test_approved_channel_preserved(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        bu = get_bu_profile("bu_alpha")  # channels: [teams, email]
        output = _make_pushpilot_output("send_now")
        assert output.channel == DeliveryChannel.TEAMS
        from pulsecraft.config.loader import get_policy

        with MagicMock():
            from unittest.mock import patch

            with patch("pulsecraft.orchestrator.engine.datetime") as mock_dt:
                mock_dt.now.return_value = datetime(2026, 4, 22, 14, 0, 0, tzinfo=UTC)
                mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
                result = orch._enforce_pushpilot_policy(
                    str(uuid.uuid4()), "bu_alpha", output, bu, get_policy()
                )

        assert result.channel == DeliveryChannel.TEAMS

    def test_unapproved_channel_replaced(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        bu = get_bu_profile("bu_alpha")  # channels: [teams, email] — no servicenow
        now = datetime.now(UTC)
        output = PushPilotOutput(
            decision=DeliveryDecision.SEND_NOW,
            channel=DeliveryChannel.SERVICENOW,  # not in bu_alpha's channels
            scheduled_time=None,
            reason="Test.",
            confidence_score=0.88,
            gate_decision=Decision(
                gate=6,
                verb=DecisionVerb.SEND_NOW,
                reason="Test.",
                confidence=0.88,
                decided_at=now,
                agent=DecisionAgent(name="pushpilot", version="1.0"),
            ),
        )
        from pulsecraft.config.loader import get_policy

        with MagicMock():
            from unittest.mock import patch

            with patch("pulsecraft.orchestrator.engine.datetime") as mock_dt:
                mock_dt.now.return_value = datetime(2026, 4, 22, 14, 0, 0, tzinfo=UTC)
                mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
                result = orch._enforce_pushpilot_policy(
                    str(uuid.uuid4()), "bu_alpha", output, bu, get_policy()
                )

        # Should fall back to teams (first approved channel for bu_alpha)
        assert result.channel in (DeliveryChannel.TEAMS, DeliveryChannel.EMAIL)

    def test_digest_decision_skips_channel_enforcement(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        bu = get_bu_profile("bu_alpha")
        now = datetime.now(UTC)
        output = PushPilotOutput(
            decision=DeliveryDecision.DIGEST,
            channel=DeliveryChannel.EMAIL,
            scheduled_time=None,
            reason="P2 + digest opt-in.",
            confidence_score=0.80,
            gate_decision=Decision(
                gate=6,
                verb=DecisionVerb.DIGEST,
                reason="P2 + digest opt-in.",
                confidence=0.80,
                decided_at=now,
                agent=DecisionAgent(name="pushpilot", version="1.0"),
            ),
        )
        from pulsecraft.config.loader import get_policy

        with MagicMock():
            from unittest.mock import patch

            with patch("pulsecraft.orchestrator.engine.datetime") as mock_dt:
                mock_dt.now.return_value = datetime(2026, 4, 22, 14, 0, 0, tzinfo=UTC)
                mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
                result = orch._enforce_pushpilot_policy(
                    str(uuid.uuid4()), "bu_alpha", output, bu, get_policy()
                )

        assert result.decision == DeliveryDecision.DIGEST


# ── DIGEST and HOLD_UNTIL respected ───────────────────────────────────────────


class TestPolicyEnforcementRespected:
    def test_digest_respected(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        bu = get_bu_profile("bu_alpha")
        now = datetime.now(UTC)
        output = PushPilotOutput(
            decision=DeliveryDecision.DIGEST,
            channel=DeliveryChannel.EMAIL,
            scheduled_time=None,
            reason="P2 digest.",
            confidence_score=0.82,
            gate_decision=Decision(
                gate=6,
                verb=DecisionVerb.DIGEST,
                reason="P2 digest.",
                confidence=0.82,
                decided_at=now,
                agent=DecisionAgent(name="pushpilot", version="1.0"),
            ),
        )
        from pulsecraft.config.loader import get_policy

        with MagicMock():
            from unittest.mock import patch

            with patch("pulsecraft.orchestrator.engine.datetime") as mock_dt:
                mock_dt.now.return_value = datetime(2026, 4, 22, 14, 0, 0, tzinfo=UTC)
                mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
                result = orch._enforce_pushpilot_policy(
                    str(uuid.uuid4()), "bu_alpha", output, bu, get_policy()
                )
        assert result.decision == DeliveryDecision.DIGEST

    def test_escalate_respected(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        bu = get_bu_profile("bu_alpha")
        now = datetime.now(UTC)
        output = PushPilotOutput(
            decision=DeliveryDecision.ESCALATE,
            channel=None,
            scheduled_time=None,
            reason="Uncertain timing.",
            confidence_score=0.55,
            gate_decision=Decision(
                gate=6,
                verb=DecisionVerb.ESCALATE,
                reason="Uncertain timing.",
                confidence=0.55,
                decided_at=now,
                agent=DecisionAgent(name="pushpilot", version="1.0"),
            ),
        )
        from pulsecraft.config.loader import get_policy

        with MagicMock():
            from unittest.mock import patch

            with patch("pulsecraft.orchestrator.engine.datetime") as mock_dt:
                mock_dt.now.return_value = datetime(2026, 4, 22, 14, 0, 0, tzinfo=UTC)
                mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
                result = orch._enforce_pushpilot_policy(
                    str(uuid.uuid4()), "bu_alpha", output, bu, get_policy()
                )
        assert result.decision == DeliveryDecision.ESCALATE
