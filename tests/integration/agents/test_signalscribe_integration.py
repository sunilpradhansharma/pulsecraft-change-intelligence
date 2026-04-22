"""Integration tests for SignalScribe — real Anthropic API calls.

Skipped by default. Run with:
    PULSECRAFT_RUN_LLM_TESTS=1 .venv/bin/pytest tests/integration/agents/ -v -m llm

Each test invokes real SignalScribe against one fixture and verifies the
ChangeBrief contract is satisfied. Specific decision verbs are NOT asserted
here — that's the eval script's job. These tests verify structural correctness.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from pulsecraft.agents.signalscribe import SignalScribe
from pulsecraft.schemas.change_artifact import ChangeArtifact
from pulsecraft.schemas.change_brief import ChangeBrief

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "changes"

_LLM_ENABLED = os.environ.get("PULSECRAFT_RUN_LLM_TESTS", "").strip() not in ("", "0")

_FIXTURE_NAMES = [
    "change_001_clearcut_communicate.json",
    "change_002_pure_internal_refactor.json",
    "change_003_ambiguous_escalate.json",
    "change_004_early_flag_hold_until.json",
    "change_005_muddled_need_clarification.json",
    "change_006_multi_bu_affected_vs_adjacent.json",
    "change_007_mlr_sensitive.json",
    "change_008_post_hoc_already_shipped.json",
]


@pytest.fixture(scope="module")
def signalscribe() -> SignalScribe:
    return SignalScribe()


@pytest.mark.llm
@pytest.mark.skipif(not _LLM_ENABLED, reason="Set PULSECRAFT_RUN_LLM_TESTS=1 to run LLM tests")
@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_returns_valid_change_brief(signalscribe: SignalScribe, fixture_name: str) -> None:
    artifact = ChangeArtifact.model_validate(json.loads((FIXTURES_DIR / fixture_name).read_text()))
    brief = signalscribe.invoke(artifact)

    # Structural contract
    assert isinstance(brief, ChangeBrief)
    assert brief.change_id == artifact.change_id
    assert brief.produced_by.agent == "signalscribe"
    assert len(brief.decisions) >= 1
    assert 0.0 <= brief.confidence_score <= 1.0

    # Decisions are for valid gates
    for decision in brief.decisions:
        assert decision.gate in (1, 2, 3)
        assert 0.0 <= decision.confidence <= 1.0
        assert decision.agent.name == "signalscribe"

    # Decisions are in order
    gates = [d.gate for d in brief.decisions]
    assert gates == sorted(gates), f"Decisions not in gate order: {gates}"


@pytest.mark.llm
@pytest.mark.skipif(not _LLM_ENABLED, reason="Set PULSECRAFT_RUN_LLM_TESTS=1 to run LLM tests")
@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_source_citations_are_real_substrings(
    signalscribe: SignalScribe, fixture_name: str
) -> None:
    """Every source citation quote must be a verbatim substring of raw_text."""
    artifact = ChangeArtifact.model_validate(json.loads((FIXTURES_DIR / fixture_name).read_text()))
    brief = signalscribe.invoke(artifact)

    for citation in brief.sources:
        assert citation.quote in artifact.raw_text, (
            f"Hallucinated citation in {fixture_name}: quote '{citation.quote[:60]}' "
            f"not found in raw_text"
        )
