"""Unit tests for SignalScribe — mocked Anthropic client, no real API calls."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from anthropic.types import TextBlock, Usage

from pulsecraft.agents.signalscribe import (
    AgentInvocationError,
    AgentOutputValidationError,
    SignalScribe,
)
from pulsecraft.orchestrator.agent_protocol import SignalScribeProtocol
from pulsecraft.schemas.change_artifact import ChangeArtifact
from pulsecraft.schemas.change_brief import ChangeBrief

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "changes"


def _make_artifact() -> ChangeArtifact:
    return ChangeArtifact.model_validate(
        json.loads((FIXTURES_DIR / "change_001_clearcut_communicate.json").read_text())
    )


def _valid_change_brief_dict(change_id: str) -> dict:
    now = datetime.now(tz=UTC).isoformat()
    return {
        "schema_version": "1.0",
        "brief_id": str(uuid.uuid4()),
        "change_id": change_id,
        "produced_at": now,
        "produced_by": {"agent": "signalscribe", "version": "1.0"},
        "summary": "The HCP portal form validation UI was redesigned.",
        "before": "Single-page form with inline errors.",
        "after": "Multi-step validation with real-time field checking.",
        "change_type": "behavior_change",
        "impact_areas": ["specialty_pharmacy", "hcp_portal_ordering"],
        "affected_segments": ["hcp_users"],
        "timeline": {
            "status": "ripe",
            "start_date": None,
            "ramp": None,
            "reevaluate_at": None,
            "reevaluate_trigger": None,
        },
        "required_actions": ["Notify field teams of new UI flow."],
        "risks": [],
        "mitigations": [],
        "faq": [
            {"q": "Does this affect my team?", "a": "Yes, if they submit prior authorizations."}
        ],
        "sources": [
            {
                "type": "release_note",
                "ref": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
                "quote": "redesigned validation interface",
            }
        ],
        "confidence_score": 0.92,
        "decisions": [
            {
                "gate": 1,
                "verb": "COMMUNICATE",
                "reason": "Visible UI change affecting HCP portal users.",
                "confidence": 0.92,
                "decided_at": now,
                "agent": {"name": "signalscribe", "version": "1.0"},
                "payload": None,
            },
            {
                "gate": 2,
                "verb": "RIPE",
                "reason": "GA rollout in progress.",
                "confidence": 0.90,
                "decided_at": now,
                "agent": {"name": "signalscribe", "version": "1.0"},
                "payload": None,
            },
            {
                "gate": 3,
                "verb": "READY",
                "reason": "Before/after clearly described.",
                "confidence": 0.92,
                "decided_at": now,
                "agent": {"name": "signalscribe", "version": "1.0"},
                "payload": None,
            },
        ],
        "open_questions": [],
        "escalation_reason": None,
    }


def _mock_message(text: str, input_tokens: int = 500, output_tokens: int = 800) -> MagicMock:
    usage = MagicMock(spec=Usage)
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    content_block = TextBlock(type="text", text=text)
    msg = MagicMock()
    msg.content = [content_block]
    msg.usage = usage
    return msg


class TestSignalScribeProtocolCompliance:
    def test_satisfies_protocol(self) -> None:
        ss = SignalScribe.__new__(SignalScribe)
        ss._model = "claude-sonnet-4-6"
        ss._max_validation_retries = 1
        ss._client = MagicMock()
        ss._system_prompt = "test"
        assert isinstance(ss, SignalScribeProtocol)

    def test_agent_name_is_canonical(self) -> None:
        assert SignalScribe.agent_name == "signalscribe"

    def test_version_is_string(self) -> None:
        assert isinstance(SignalScribe.version, str)


class TestSignalScribeInit:
    def test_loads_prompt_from_default_path(self) -> None:
        with patch("anthropic.Anthropic"):
            ss = SignalScribe()
        assert len(ss._system_prompt) > 100

    def test_raises_if_prompt_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            SignalScribe(prompt_path=tmp_path / "nonexistent.md")

    def test_loads_prompt_from_custom_path(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("# Test prompt", encoding="utf-8")
        with patch("anthropic.Anthropic"):
            ss = SignalScribe(prompt_path=prompt_file)
        assert ss._system_prompt == "# Test prompt"

    def test_uses_provided_client(self) -> None:
        mock_client = MagicMock()
        ss = SignalScribe(anthropic_client=mock_client)
        assert ss._client is mock_client


class TestSignalScribeInvoke:
    def test_returns_valid_change_brief(self) -> None:
        artifact = _make_artifact()
        valid_json = json.dumps(_valid_change_brief_dict(artifact.change_id))
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_message(valid_json)
        ss = SignalScribe(anthropic_client=mock_client)
        result = ss.invoke(artifact)
        assert isinstance(result, ChangeBrief)
        assert result.change_id == artifact.change_id

    def test_decisions_array_is_populated(self) -> None:
        artifact = _make_artifact()
        valid_json = json.dumps(_valid_change_brief_dict(artifact.change_id))
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_message(valid_json)
        ss = SignalScribe(anthropic_client=mock_client)
        result = ss.invoke(artifact)
        assert len(result.decisions) >= 1

    def test_decisions_agent_name_is_canonical(self) -> None:
        artifact = _make_artifact()
        valid_json = json.dumps(_valid_change_brief_dict(artifact.change_id))
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_message(valid_json)
        ss = SignalScribe(anthropic_client=mock_client)
        result = ss.invoke(artifact)
        for decision in result.decisions:
            assert decision.agent.name == "signalscribe"

    def test_strips_markdown_fences(self) -> None:
        artifact = _make_artifact()
        valid_dict = _valid_change_brief_dict(artifact.change_id)
        fenced = "```json\n" + json.dumps(valid_dict) + "\n```"
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_message(fenced)
        ss = SignalScribe(anthropic_client=mock_client)
        result = ss.invoke(artifact)
        assert isinstance(result, ChangeBrief)

    def test_fixes_wrong_change_id(self) -> None:
        artifact = _make_artifact()
        brief_dict = _valid_change_brief_dict(artifact.change_id)
        brief_dict["change_id"] = "00000000-0000-0000-0000-000000000000"
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_message(json.dumps(brief_dict))
        ss = SignalScribe(anthropic_client=mock_client)
        result = ss.invoke(artifact)
        assert result.change_id == artifact.change_id


class TestSignalScribeRetry:
    def test_retries_once_on_invalid_json(self) -> None:
        artifact = _make_artifact()
        valid_json = json.dumps(_valid_change_brief_dict(artifact.change_id))
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _mock_message("not valid json at all"),
            _mock_message(valid_json),
        ]
        ss = SignalScribe(anthropic_client=mock_client, max_validation_retries=1)
        result = ss.invoke(artifact)
        assert isinstance(result, ChangeBrief)
        assert mock_client.messages.create.call_count == 2

    def test_retries_once_on_schema_validation_failure(self) -> None:
        artifact = _make_artifact()
        invalid_dict = _valid_change_brief_dict(artifact.change_id)
        invalid_dict["confidence_score"] = 999.9  # out of range
        valid_json = json.dumps(_valid_change_brief_dict(artifact.change_id))
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _mock_message(json.dumps(invalid_dict)),
            _mock_message(valid_json),
        ]
        ss = SignalScribe(anthropic_client=mock_client, max_validation_retries=1)
        result = ss.invoke(artifact)
        assert isinstance(result, ChangeBrief)

    def test_raises_validation_error_after_max_retries(self) -> None:
        artifact = _make_artifact()
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_message("not json")
        ss = SignalScribe(anthropic_client=mock_client, max_validation_retries=1)
        with pytest.raises(AgentOutputValidationError):
            ss.invoke(artifact)

    def test_raises_invocation_error_on_auth_failure(self) -> None:
        import anthropic as anthropic_lib

        artifact = _make_artifact()
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic_lib.AuthenticationError(
            message="Invalid API key", response=MagicMock(), body={}
        )
        ss = SignalScribe(anthropic_client=mock_client)
        with pytest.raises(AgentInvocationError):
            ss.invoke(artifact)


class TestSignalScribeSources:
    def test_confidence_score_in_range(self) -> None:
        artifact = _make_artifact()
        valid_json = json.dumps(_valid_change_brief_dict(artifact.change_id))
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_message(valid_json)
        ss = SignalScribe(anthropic_client=mock_client)
        result = ss.invoke(artifact)
        assert 0.0 <= result.confidence_score <= 1.0

    def test_produces_by_has_correct_agent_name(self) -> None:
        artifact = _make_artifact()
        valid_json = json.dumps(_valid_change_brief_dict(artifact.change_id))
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_message(valid_json)
        ss = SignalScribe(anthropic_client=mock_client)
        result = ss.invoke(artifact)
        assert result.produced_by.agent == "signalscribe"
