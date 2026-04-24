"""Registry skill — BU candidate lookup for the pre-filter stage."""

from __future__ import annotations

from pulsecraft.schemas.bu_registry import BURegistry
from pulsecraft.schemas.change_brief import ChangeBrief


def _to_snake(s: str) -> str:
    """Normalise an impact_area to snake_case for registry matching.

    SignalScribe sometimes emits two-word English phrases like "analytics portal"
    instead of the registered identifier "analytics_portal". Converting spaces
    to underscores (and lower-casing) makes these match.
    """
    return s.lower().strip().replace(" ", "_").replace("-", "_")


def _to_space(s: str) -> str:
    """Normalise a registry keyword or impact_area to space-separated lowercase."""
    return s.lower().replace("_", " ").strip()


def lookup_bu_candidates(change_brief: ChangeBrief, registry: BURegistry) -> list[str]:
    """Return BU IDs whose owned_product_areas intersect change_brief.impact_areas.

    Primary pass: exact match on owned_product_areas, with space→underscore
    normalisation so that SignalScribe phrases like "analytics portal" match
    the registered identifier "analytics_portal".

    Fallback pass: if the primary pass finds no candidates, try keyword equality
    after normalising both BU keywords and impact_areas to space-separated
    lowercase. This handles cases like "analytics" matching bu_zeta.

    Recall-biased: prefer over-matching; BUAtlas (gate 4) applies precision.
    Returns BU IDs in registry order.
    """
    raw_impact = set(change_brief.impact_areas)
    if not raw_impact:
        return []

    # Extend with space→underscore variants so "analytics portal" → "analytics_portal"
    normalised_impact = raw_impact | {_to_snake(a) for a in raw_impact}

    # Primary pass: exact match (including normalised variants)
    candidates: list[str] = []
    for entry in registry.bus:
        owned = set(entry.owned_product_areas)
        if owned & normalised_impact:
            candidates.append(entry.bu_id)

    if candidates:
        return candidates

    # Fallback pass: keyword equality after space-normalisation
    spaced_impact = {_to_space(a) for a in raw_impact}
    for entry in registry.bus:
        for kw in entry.keywords:
            if _to_space(kw) in spaced_impact:
                candidates.append(entry.bu_id)
                break

    return candidates
