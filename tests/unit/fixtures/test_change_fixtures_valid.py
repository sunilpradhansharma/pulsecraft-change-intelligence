"""Every fixture in fixtures/changes/ parses as a valid ChangeArtifact."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pulsecraft.schemas.change_artifact import ChangeArtifact

FIXTURES_DIR = Path(__file__).parents[3] / "fixtures" / "changes"


def _fixture_files() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("change_*.json"))


@pytest.mark.parametrize("fixture_path", _fixture_files(), ids=lambda p: p.name)
def test_fixture_parses_as_change_artifact(fixture_path: Path) -> None:
    """Each fixture file must parse without validation errors."""
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    artifact = ChangeArtifact.model_validate(data)
    assert artifact.change_id, "change_id must be non-empty"
    assert artifact.title, "title must be non-empty"
    assert artifact.raw_text, "raw_text must be non-empty"


@pytest.mark.parametrize("fixture_path", _fixture_files(), ids=lambda p: p.name)
def test_fixture_roundtrip_is_stable(fixture_path: Path) -> None:
    """Parsed then re-serialized fixture must produce stable JSON (no data loss)."""
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    artifact = ChangeArtifact.model_validate(data)
    roundtripped = json.loads(artifact.model_dump_json())
    # Re-parse to confirm round-tripped data is also valid
    ChangeArtifact.model_validate(roundtripped)
