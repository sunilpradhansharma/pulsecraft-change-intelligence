"""ChangeArtifact schema — normalized ingest output, SignalScribe input."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

UUIDStr = Annotated[
    str,
    Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"),
]


class SourceType(StrEnum):
    """Types of upstream change artifact sources."""

    RELEASE_NOTE = "release_note"
    JIRA_WORK_ITEM = "jira_work_item"
    ADO_WORK_ITEM = "ado_work_item"
    DOC = "doc"
    FEATURE_FLAG = "feature_flag"
    INCIDENT = "incident"


class RelationKind(StrEnum):
    """Relationship between two artifacts."""

    PARENT = "parent"
    CHILD = "child"
    REFERENCED_BY = "referenced-by"
    REFERENCES = "references"


class Author(BaseModel):
    """Author attribution — display name only, no email or employee ID."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    name: str = Field(description="Author display name. Must not be an email address.")
    role: str | None = Field(default=None, description="Organizational role title.")


class RelatedRef(BaseModel):
    """A reference to a related artifact in the same or another source system."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    type: SourceType = Field(description="Source system type of the related artifact.")
    ref: str = Field(description="Opaque reference identifier in the source system.")
    relation: RelationKind = Field(
        description="Relationship from this artifact to the related one."
    )


class RolloutHints(BaseModel):
    """Optional rollout metadata extracted from the source artifact."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    start_date: str | None = Field(
        default=None,
        description="ISO-8601 date when rollout is scheduled to begin (YYYY-MM-DD).",
    )
    ramp: str | None = Field(
        default=None,
        description="Free-text rollout ramp description (e.g., '1% internal → 10% → GA over 30 days').",
    )
    target_population: str | None = Field(
        default=None,
        description="Free-text target population description (e.g., 'US HCP portal users').",
    )


class ChangeArtifact(BaseModel):
    """Normalized change artifact — the output of ingest adapters, input to SignalScribe.

    Shape is identical regardless of source system. All content has been redacted of
    PII, PHI, and secrets by the ingest hook before this model is populated.
    """

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    schema_version: str = Field(default="1.0", description="Schema version. Must be '1.0'.")
    change_id: UUIDStr = Field(
        description="UUID v4. Generated at ingest time. Stable across all downstream contracts."
    )
    source_type: SourceType = Field(description="Type of the originating source artifact.")
    source_ref: str = Field(
        description="Opaque source-system identifier. Must not include URLs with credentials."
    )
    ingested_at: AwareDatetime = Field(
        description="UTC timestamp when this artifact was ingested. Naive datetimes are rejected."
    )
    title: str = Field(max_length=500, description="Display title of the change. Redacted of PII.")
    raw_text: str = Field(
        description="Redacted full text of the change artifact. The ingest hook MUST remove "
        "all PII, PHI, credentials, and secrets before this field is populated."
    )
    author: Author | None = Field(
        default=None, description="Optional author attribution. Display name only."
    )
    related_refs: list[RelatedRef] = Field(
        default_factory=list,
        description="References to related artifacts in the same or other source systems.",
    )
    links: list[str] = Field(
        default_factory=list,
        description="Opaque internal URIs. Must not include query-string secrets or tokens.",
    )
    labels: list[str] = Field(
        default_factory=list,
        description="Structured tags from the source system.",
    )
    rollout_hints: RolloutHints | None = Field(
        default=None, description="Optional rollout metadata."
    )
