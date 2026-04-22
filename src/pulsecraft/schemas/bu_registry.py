"""BURegistry schema — product-area to BU mapping for deterministic pre-filter."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BURegistryEntry(BaseModel):
    """Single BU entry in the registry."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    bu_id: str = Field(
        pattern=r"^[a-z][a-z0-9_-]*$",
        description="Stable lowercase BU identifier.",
    )
    name: str = Field(description="Human-readable BU display name.")
    owned_product_areas: list[str] = Field(
        min_length=1,
        description="Product areas owned by this BU.",
    )
    keywords: list[str] = Field(
        min_length=1,
        description="Natural-language phrases for fuzzy pre-filter matching.",
    )
    therapeutic_area: str | None = Field(
        default=None,
        description="Primary therapeutic area. Null until taxonomy is loaded.",
    )


class BURegistry(BaseModel):
    """BU registry — deterministic pre-filter between SignalScribe and BUAtlas.

    Recall-biased: prefer over-matching; BUAtlas (gate 4) applies precision.
    """

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    schema_version: str = Field(default="1.0")
    bus: list[BURegistryEntry] = Field(
        min_length=1,
        description="All registered BUs.",
    )
