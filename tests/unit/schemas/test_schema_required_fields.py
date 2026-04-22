"""Assert that removing any required field from a fixture causes schema validation to fail."""

from __future__ import annotations

import json

import jsonschema
import pytest
from referencing import Registry

from tests.unit.schemas.conftest import FIXTURES_DIR, SCHEMA_FILES, make_validator

SCHEMAS_WITH_FIXTURES = [
    ("change_artifact", "change_artifact.json"),
    ("change_brief", "change_brief.json"),
    ("personalized_brief", "personalized_brief.json"),
    ("delivery_plan", "delivery_plan.json"),
    ("bu_profile", "bu_profile.json"),
    ("audit_record", "audit_record.json"),
]


@pytest.mark.parametrize("schema_name,fixture_file", SCHEMAS_WITH_FIXTURES)
def test_required_fields_present_passes(
    schema_name: str, fixture_file: str, schema_registry: Registry
) -> None:
    """The full fixture must pass schema validation."""
    data = json.loads((FIXTURES_DIR / fixture_file).read_text())
    schema = json.loads(SCHEMA_FILES[schema_name].read_text())
    make_validator(schema, schema_registry).validate(data)


@pytest.mark.parametrize("schema_name,fixture_file", SCHEMAS_WITH_FIXTURES)
def test_removing_required_field_fails(
    schema_name: str, fixture_file: str, schema_registry: Registry
) -> None:
    """Removing any required field must cause schema validation to fail."""
    data = json.loads((FIXTURES_DIR / fixture_file).read_text())
    schema = json.loads(SCHEMA_FILES[schema_name].read_text())
    required_fields = schema.get("required", [])
    assert required_fields, f"Schema {schema_name} has no required fields listed"

    validator = make_validator(schema, schema_registry)
    for field in required_fields:
        if field not in data:
            continue  # fixture doesn't have this field at top level; skip
        truncated = {k: v for k, v in data.items() if k != field}
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(truncated)
