"""Unit tests for PushPilot — mocked client, no real API calls."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import anthropic
import pytest

from pulsecraft.agents.pushpilot import (
    AgentInvocationError,
    AgentOutputValidationError,
    PushPilot,
)
from pulsecraft.config.loader import get_bu_profile
from pulsecraft.orchestrator.agent_protocol import PushPilotProtocol
from pulsecraft.schemas.delivery_plan import DeliveryDecision
from pulsecraft.schemas.push_pilot_output import PushPilotOutput

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "changes"


def _make_personalized_brief(priority: str = "P1"):
    """Build a minimal PersonalizedBrief for testing."""
    from pulsecraft.schemas.decision import Decision, DecisionAgent, DecisionVerb
    from pulsecraft.schemas.personalized_brief import (
        MessageQuality,
        MessageVariants,
        PersonalizedBrief,
        Priority,
        ProducedBy,
        RecommendedAction,
        Relevance,
    )

    now = datetime.now(UTC)
    agent = DecisionAgent(name="buatlas", version="1.0")
    priority_map = {"P0": Priority.P0, "P1": Priority.P1, "P2": Priority.P2}
    return PersonalizedBrief(
        personalized_brief_id=str(uuid.uuid4()),
        change_id=str(uuid.uuid4()),
        brief_id=str(uuid.uuid4()),
        bu_id="bu_alpha",
        produced_at=now,
        produced_by=ProducedBy(version="1.0", invocation_id=str(uuid.uuid4())),
        relevance=Relevance.AFFECTED,
        priority=priority_map.get(priority, Priority.P1),
        why_relevant="Mock: BU affected by this change.",
        recommended_actions=[RecommendedAction(owner="BU head", action="Review the change.")],
        assumptions=["Mock assumption."],
        message_variants=MessageVariants(
            push_short="Change alert: prior auth form updated.",
            teams_medium="A change affecting your BU has been processed.",
            email_long="Full email: Please review the change affecting your BU.",
        ),
        message_quality=MessageQuality.WORTH_SENDING,
        confidence_score=0.85,
        decisions=[
            Decision(
                gate=4,
                verb=DecisionVerb.AFFECTED,
                reason="Mock: affected.",
                confidence=0.85,
                decided_at=now,
                agent=agent,
            ),
            Decision(
                gate=5,
                verb=DecisionVerb.WORTH_SENDING,
                reason="Mock: worth sending.",
                confidence=0.85,
                decided_at=now,
                agent=agent,
            ),
        ],
        regeneration_attempts=0,
    )


def _make_pushpilot_response_json(decision: str = "send_now", channel: str = "teams") -> str:
    """Build a valid PushPilotOutput JSON string."""
    now = datetime.now(UTC)
    scheduled = None
    if decision == "hold_until":
        scheduled = (now + timedelta(hours=12)).isoformat()
    return json.dumps(
        {
            "decision": decision,
            "channel": channel if decision != "escalate" else None,
            "scheduled_time": scheduled,
            "reason": f"Mock: {decision} because working hours and P1 priority.",
            "confidence_score": 0.88,
            "gate_decision": {
                "gate": 6,
                "verb": decision.upper(),
                "reason": f"Mock: {decision}.",
                "confidence": 0.88,
                "decided_at": now.isoformat(),
                "agent": {"name": "pushpilot", "version": "1.0"},
            },
        }
    )


def _mock_client_with_response(response_text: str) -> anthropic.Anthropic:
    """Return a mock Anthropic client that yields response_text."""
    from anthropic.types import TextBlock

    mock_client = MagicMock(spec=anthropic.Anthropic)
    mock_response = MagicMock()
    mock_response.content = [TextBlock(type="text", text=response_text)]
    mock_response.usage = MagicMock(input_tokens=1000, output_tokens=500)
    mock_client.messages.create.return_value = mock_response
    return mock_client


# ── Protocol compliance ────────────────────────────────────────────────────────


class TestPushPilotProtocol:
    def test_satisfies_protocol(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "pushpilot.md"
        prompt_file.write_text("# PushPilot test prompt")
        agent = PushPilot(anthropic_client=MagicMock(), prompt_path=prompt_file)
        assert isinstance(agent, PushPilotProtocol)

    def test_agent_name(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "pushpilot.md"
        prompt_file.write_text("# prompt")
        agent = PushPilot(anthropic_client=MagicMock(), prompt_path=prompt_file)
        assert agent.agent_name == "pushpilot"

    def test_version(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "pushpilot.md"
        prompt_file.write_text("# prompt")
        agent = PushPilot(anthropic_client=MagicMock(), prompt_path=prompt_file)
        assert agent.version == "1.0"


# ── Initialisation ─────────────────────────────────────────────────────────────


class TestPushPilotInit:
    def test_loads_prompt_from_default_path(self) -> None:
        default_path = (
            Path(__file__).parent.parent.parent.parent / ".claude" / "agents" / "pushpilot.md"
        )
        assert default_path.exists(), "pushpilot.md system prompt must exist"
        agent = PushPilot(anthropic_client=MagicMock())
        assert len(agent._system_prompt) > 100

    def test_missing_prompt_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="PushPilot"):
            PushPilot(anthropic_client=MagicMock(), prompt_path=tmp_path / "missing.md")

    def test_custom_prompt_path(self, tmp_path: Path) -> None:
        p = tmp_path / "custom.md"
        p.write_text("# Custom PushPilot")
        agent = PushPilot(anthropic_client=MagicMock(), prompt_path=p)
        assert "Custom PushPilot" in agent._system_prompt

    def test_client_injection(self, tmp_path: Path) -> None:
        mock_client = MagicMock(spec=anthropic.Anthropic)
        prompt_file = tmp_path / "p.md"
        prompt_file.write_text("# p")
        agent = PushPilot(anthropic_client=mock_client, prompt_path=prompt_file)
        assert agent._client is mock_client


# ── Invoke contract ────────────────────────────────────────────────────────────


class TestPushPilotInvokeContract:
    def test_returns_push_pilot_output(self, tmp_path: Path) -> None:
        pb = _make_personalized_brief()
        bu = get_bu_profile("bu_alpha")
        prompt_file = tmp_path / "p.md"
        prompt_file.write_text("# p")
        client = _mock_client_with_response(_make_pushpilot_response_json("send_now"))
        agent = PushPilot(anthropic_client=client, prompt_path=prompt_file)
        result = agent.invoke(pb, bu)
        assert isinstance(result, PushPilotOutput)

    def test_gate_decision_gate_is_6(self, tmp_path: Path) -> None:
        pb = _make_personalized_brief()
        bu = get_bu_profile("bu_alpha")
        prompt_file = tmp_path / "p.md"
        prompt_file.write_text("# p")
        client = _mock_client_with_response(_make_pushpilot_response_json("send_now"))
        agent = PushPilot(anthropic_client=client, prompt_path=prompt_file)
        result = agent.invoke(pb, bu)
        assert result.gate_decision.gate == 6

    def test_confidence_in_range(self, tmp_path: Path) -> None:
        pb = _make_personalized_brief()
        bu = get_bu_profile("bu_alpha")
        prompt_file = tmp_path / "p.md"
        prompt_file.write_text("# p")
        client = _mock_client_with_response(_make_pushpilot_response_json("send_now"))
        agent = PushPilot(anthropic_client=client, prompt_path=prompt_file)
        result = agent.invoke(pb, bu)
        assert 0.0 <= result.confidence_score <= 1.0

    def test_agent_name_in_gate_decision(self, tmp_path: Path) -> None:
        pb = _make_personalized_brief()
        bu = get_bu_profile("bu_alpha")
        prompt_file = tmp_path / "p.md"
        prompt_file.write_text("# p")
        client = _mock_client_with_response(_make_pushpilot_response_json("send_now"))
        agent = PushPilot(anthropic_client=client, prompt_path=prompt_file)
        result = agent.invoke(pb, bu)
        assert result.gate_decision.agent.name == "pushpilot"

    def test_send_now_has_no_scheduled_time(self, tmp_path: Path) -> None:
        pb = _make_personalized_brief()
        bu = get_bu_profile("bu_alpha")
        prompt_file = tmp_path / "p.md"
        prompt_file.write_text("# p")
        client = _mock_client_with_response(_make_pushpilot_response_json("send_now"))
        agent = PushPilot(anthropic_client=client, prompt_path=prompt_file)
        result = agent.invoke(pb, bu)
        assert result.decision == DeliveryDecision.SEND_NOW
        assert result.scheduled_time is None

    def test_hold_until_has_scheduled_time(self, tmp_path: Path) -> None:
        pb = _make_personalized_brief()
        bu = get_bu_profile("bu_alpha")
        prompt_file = tmp_path / "p.md"
        prompt_file.write_text("# p")
        client = _mock_client_with_response(_make_pushpilot_response_json("hold_until"))
        agent = PushPilot(anthropic_client=client, prompt_path=prompt_file)
        result = agent.invoke(pb, bu)
        assert result.decision == DeliveryDecision.HOLD_UNTIL
        assert result.scheduled_time is not None

    def test_digest_decision(self, tmp_path: Path) -> None:
        pb = _make_personalized_brief("P2")
        bu = get_bu_profile("bu_alpha")
        prompt_file = tmp_path / "p.md"
        prompt_file.write_text("# p")
        client = _mock_client_with_response(_make_pushpilot_response_json("digest"))
        agent = PushPilot(anthropic_client=client, prompt_path=prompt_file)
        result = agent.invoke(pb, bu)
        assert result.decision == DeliveryDecision.DIGEST

    def test_escalate_has_null_channel(self, tmp_path: Path) -> None:
        pb = _make_personalized_brief()
        bu = get_bu_profile("bu_alpha")
        prompt_file = tmp_path / "p.md"
        prompt_file.write_text("# p")
        client = _mock_client_with_response(_make_pushpilot_response_json("escalate"))
        agent = PushPilot(anthropic_client=client, prompt_path=prompt_file)
        result = agent.invoke(pb, bu)
        assert result.decision == DeliveryDecision.ESCALATE
        assert result.channel is None

    def test_markdown_fence_stripped(self, tmp_path: Path) -> None:
        pb = _make_personalized_brief()
        bu = get_bu_profile("bu_alpha")
        prompt_file = tmp_path / "p.md"
        prompt_file.write_text("# p")
        raw = _make_pushpilot_response_json("send_now")
        wrapped = f"```json\n{raw}\n```"
        client = _mock_client_with_response(wrapped)
        agent = PushPilot(anthropic_client=client, prompt_path=prompt_file)
        result = agent.invoke(pb, bu)
        assert isinstance(result, PushPilotOutput)


# ── Retry and error handling ───────────────────────────────────────────────────


class TestPushPilotRetry:
    def test_invalid_json_triggers_validation_retry(self, tmp_path: Path) -> None:
        pb = _make_personalized_brief()
        bu = get_bu_profile("bu_alpha")
        prompt_file = tmp_path / "p.md"
        prompt_file.write_text("# p")
        mock_client = MagicMock(spec=anthropic.Anthropic)
        usage_mock = MagicMock(input_tokens=500, output_tokens=200)
        good_response = _make_pushpilot_response_json("send_now")

        call_count = [0]

        def side_effect(*args, **kwargs):
            from anthropic.types import TextBlock

            call_count[0] += 1
            response = MagicMock()
            response.usage = usage_mock
            if call_count[0] == 1:
                response.content = [TextBlock(type="text", text="not valid json at all")]
            else:
                response.content = [TextBlock(type="text", text=good_response)]
            return response

        mock_client.messages.create.side_effect = side_effect
        agent = PushPilot(
            anthropic_client=mock_client, max_validation_retries=1, prompt_path=prompt_file
        )
        result = agent.invoke(pb, bu)
        assert isinstance(result, PushPilotOutput)
        assert call_count[0] == 2

    def test_persistent_invalid_json_raises_validation_error(self, tmp_path: Path) -> None:
        pb = _make_personalized_brief()
        bu = get_bu_profile("bu_alpha")
        prompt_file = tmp_path / "p.md"
        prompt_file.write_text("# p")
        mock_client = MagicMock(spec=anthropic.Anthropic)
        usage_mock = MagicMock(input_tokens=500, output_tokens=200)

        def side_effect(*args, **kwargs):
            from anthropic.types import TextBlock

            response = MagicMock()
            response.usage = usage_mock
            response.content = [TextBlock(type="text", text="not json")]
            return response

        mock_client.messages.create.side_effect = side_effect
        agent = PushPilot(
            anthropic_client=mock_client, max_validation_retries=1, prompt_path=prompt_file
        )
        with pytest.raises(AgentOutputValidationError):
            agent.invoke(pb, bu)

    def test_auth_error_raises_invocation_error(self, tmp_path: Path) -> None:
        pb = _make_personalized_brief()
        bu = get_bu_profile("bu_alpha")
        prompt_file = tmp_path / "p.md"
        prompt_file.write_text("# p")
        mock_client = MagicMock(spec=anthropic.Anthropic)
        mock_client.messages.create.side_effect = anthropic.AuthenticationError(
            message="auth error",
            response=MagicMock(status_code=401),
            body={},
        )
        agent = PushPilot(anthropic_client=mock_client, prompt_path=prompt_file)
        with pytest.raises(AgentInvocationError, match="authentication"):
            agent.invoke(pb, bu)

    def test_connection_error_raises_invocation_error(self, tmp_path: Path) -> None:
        pb = _make_personalized_brief()
        bu = get_bu_profile("bu_alpha")
        prompt_file = tmp_path / "p.md"
        prompt_file.write_text("# p")
        mock_client = MagicMock(spec=anthropic.Anthropic)
        mock_client.messages.create.side_effect = anthropic.APIConnectionError(request=MagicMock())
        agent = PushPilot(anthropic_client=mock_client, prompt_path=prompt_file)
        with pytest.raises(AgentInvocationError, match="connection"):
            agent.invoke(pb, bu)
