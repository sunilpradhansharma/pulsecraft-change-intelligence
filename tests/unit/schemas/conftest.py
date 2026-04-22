"""Shared fixtures for schema tests: JSON schema registry and fixture paths."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

SCHEMAS_DIR = Path(__file__).parents[3] / "schemas"
FIXTURES_DIR = Path(__file__).parents[2] / "fixtures" / "schemas" / "minimal_valid"

SCHEMA_FILES = {
    "change_artifact": SCHEMAS_DIR / "change_artifact.schema.json",
    "change_brief": SCHEMAS_DIR / "change_brief.schema.json",
    "personalized_brief": SCHEMAS_DIR / "personalized_brief.schema.json",
    "delivery_plan": SCHEMAS_DIR / "delivery_plan.schema.json",
    "bu_profile": SCHEMAS_DIR / "bu_profile.schema.json",
    "audit_record": SCHEMAS_DIR / "audit_record.schema.json",
    "decision": SCHEMAS_DIR / "decision.schema.json",
}


@pytest.fixture(scope="session")
def schema_registry() -> Registry:
    """jsonschema Registry containing all PulseCraft schemas for $ref resolution."""
    resources = []
    for schema_file in SCHEMA_FILES.values():
        schema = json.loads(schema_file.read_text())
        resource = Resource.from_contents(schema)
        resources.append((schema["$id"], resource))
    return Registry().with_resources(resources)


@pytest.fixture(scope="session")
def loaded_schemas() -> dict[str, dict]:
    """All JSON schemas loaded as dicts, keyed by short name."""
    return {name: json.loads(path.read_text()) for name, path in SCHEMA_FILES.items()}


def make_validator(schema: dict, registry: Registry) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(schema, registry=registry)
