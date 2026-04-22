"""Policy schema — confidence thresholds, restricted terms, HITL triggers, rate limits."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SignalScribeThresholds(BaseModel):
    """Per-gate confidence thresholds for SignalScribe decisions."""

    model_config = ConfigDict(extra="forbid")

    gate_1_communicate: float = Field(ge=0.0, le=1.0)
    gate_1_archive: float = Field(ge=0.0, le=1.0)
    gate_2_ripe: float = Field(ge=0.0, le=1.0)
    gate_3_ready: float = Field(ge=0.0, le=1.0)


class BUAtlasThresholds(BaseModel):
    """Per-gate confidence thresholds for BUAtlas decisions."""

    model_config = ConfigDict(extra="forbid")

    gate_4_affected: float = Field(ge=0.0, le=1.0)
    gate_4_any: float = Field(ge=0.0, le=1.0)
    gate_5_worth_sending: float = Field(ge=0.0, le=1.0)


class PushPilotThresholds(BaseModel):
    """Per-gate confidence thresholds for PushPilot decisions."""

    model_config = ConfigDict(extra="forbid")

    gate_6_any: float = Field(ge=0.0, le=1.0)


class ConfidenceThresholds(BaseModel):
    """All per-agent confidence thresholds; below threshold routes to HITL."""

    model_config = ConfigDict(extra="forbid")

    signalscribe: SignalScribeThresholds
    buatlas: BUAtlasThresholds
    pushpilot: PushPilotThresholds


class RestrictedTerms(BaseModel):
    """Categorized restricted terms; hook matches case-insensitively."""

    model_config = ConfigDict(extra="forbid")

    commitments_and_dates: list[str]
    scientific_communication: list[str]
    sensitive_data_markers: list[str]


class PerRecipientRateLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_per_day: int = Field(gt=0)
    max_per_week: int = Field(gt=0)


class PerBURateLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_per_day: int = Field(gt=0)


class GlobalRateLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_per_hour: int = Field(gt=0)


class RateLimits(BaseModel):
    """Notification rate limits at per-recipient, per-BU, and global scopes."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    per_recipient: PerRecipientRateLimits
    per_bu: PerBURateLimits
    # "global" is a Python keyword; alias maps the YAML key to this field name
    global_limits: GlobalRateLimits = Field(alias="global")


class QuietHoursDefault(BaseModel):
    """Default quiet hours when BU profile does not specify."""

    model_config = ConfigDict(extra="forbid")

    timezone: str = Field(description="IANA timezone identifier.")
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class Policy(BaseModel):
    """Policy configuration — confidence thresholds, restricted terms, rate limits, HITL triggers.

    Enforced in code (hooks). Agents cannot reason around these values.
    """

    model_config = ConfigDict(extra="forbid", frozen=False)

    schema_version: str = Field(default="1.0")
    confidence_thresholds: ConfidenceThresholds
    hitl_triggers: list[str]
    restricted_terms: RestrictedTerms
    rate_limits: RateLimits
    quiet_hours_default: QuietHoursDefault
    mlr_review_required_when: list[str]
