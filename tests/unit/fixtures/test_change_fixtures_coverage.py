"""Coverage guards for the fixture set: count, naming, and source_type coverage."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pulsecraft.schemas.change_artifact import SourceType

FIXTURES_DIR = Path(__file__).parents[3] / "fixtures" / "changes"

EXPECTED_FIXTURE_COUNT = 8

# Source types covered by the v1 fixture set.
V1_COVERED_SOURCE_TYPES = {
    SourceType.RELEASE_NOTE,
    SourceType.JIRA_WORK_ITEM,
    SourceType.ADO_WORK_ITEM,
    SourceType.FEATURE_FLAG,
}

# Source types explicitly deferred — no v1 eval scenarios require them.
# Candidate additions for a future prompt: doc (wiki/regulatory-change), incident (post-mortem).
V1_OUT_OF_SCOPE_SOURCE_TYPES = {
    SourceType.DOC,
    SourceType.INCIDENT,
}

FILENAME_PATTERN = re.compile(r"^change_\d{3}_[a-z_]+\.json$")


def _fixture_files() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("change_*.json"))


def test_exact_fixture_count() -> None:
    """Guard against accidental additions or deletions."""
    files = _fixture_files()
    assert len(files) == EXPECTED_FIXTURE_COUNT, (
        f"Expected {EXPECTED_FIXTURE_COUNT} fixtures, found {len(files)}: {[f.name for f in files]}"
    )


def test_fixture_filenames_match_pattern() -> None:
    for f in _fixture_files():
        assert FILENAME_PATTERN.match(f.name), (
            f"Filename {f.name!r} does not match required pattern 'change_NNN_lower_slug.json'"
        )


def test_v1_covered_source_types_are_present() -> None:
    """All four v1 source types must appear at least once across the fixture set."""
    actual_types = {SourceType(json.loads(f.read_text())["source_type"]) for f in _fixture_files()}
    for st in V1_COVERED_SOURCE_TYPES:
        assert st in actual_types, (
            f"source_type={st.value!r} is expected in the v1 fixture set but not found"
        )


def test_out_of_scope_types_are_absent() -> None:
    """doc and incident are intentionally absent from the v1 fixture set."""
    actual_types = {SourceType(json.loads(f.read_text())["source_type"]) for f in _fixture_files()}
    for st in V1_OUT_OF_SCOPE_SOURCE_TYPES:
        assert st not in actual_types, (
            f"source_type={st.value!r} was found in fixtures but is supposed to be "
            f"out-of-scope for v1. Move it to V1_COVERED_SOURCE_TYPES if intentional."
        )


def test_all_change_ids_are_unique() -> None:
    ids = [json.loads(f.read_text())["change_id"] for f in _fixture_files()]
    assert len(ids) == len(set(ids)), "Duplicate change_id values across fixture files"


def test_fixture_slugs_match_scenario_names() -> None:
    """Each fixture slug in its filename should be recognisable (non-empty, lowercase)."""
    for f in _fixture_files():
        slug = f.stem.split("_", 2)[2]  # after change_NNN_
        assert slug and slug == slug.lower(), (
            f"Fixture slug in {f.name!r} is empty or contains uppercase characters"
        )
