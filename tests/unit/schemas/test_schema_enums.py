"""Assert that DecisionVerb Python enum and decision.schema.json enum list exactly the same verbs."""

from __future__ import annotations

import json
from pathlib import Path

from pulsecraft.schemas.decision import DecisionVerb

SCHEMAS_DIR = Path(__file__).parents[3] / "schemas"


def test_decision_verb_enum_parity() -> None:
    """DecisionVerb Python StrEnum must list exactly the same verbs as decision.schema.json."""
    decision_schema = json.loads((SCHEMAS_DIR / "decision.schema.json").read_text())
    schema_verbs = set(decision_schema["properties"]["verb"]["enum"])
    python_verbs = {v.value for v in DecisionVerb}
    assert python_verbs == schema_verbs, (
        f"Enum drift detected.\n"
        f"In Python only: {python_verbs - schema_verbs}\n"
        f"In JSON schema only: {schema_verbs - python_verbs}"
    )


def test_decision_verb_no_duplicates() -> None:
    """JSON schema enum must not contain duplicates."""
    decision_schema = json.loads((SCHEMAS_DIR / "decision.schema.json").read_text())
    verbs = decision_schema["properties"]["verb"]["enum"]
    assert len(verbs) == len(set(verbs)), f"Duplicate verbs in JSON schema: {verbs}"
