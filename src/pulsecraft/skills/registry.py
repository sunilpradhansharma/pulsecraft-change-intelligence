"""Registry skill — BU candidate lookup for the pre-filter stage."""

from __future__ import annotations

from pulsecraft.schemas.bu_registry import BURegistry
from pulsecraft.schemas.change_brief import ChangeBrief


def _norm(s: str) -> str:
    """Normalise a registry term or impact_area for keyword comparison."""
    return s.lower().replace("_", " ").strip()


def lookup_bu_candidates(change_brief: ChangeBrief, registry: BURegistry) -> list[str]:
    """Return BU IDs whose owned_product_areas intersect change_brief.impact_areas.

    Primary pass: exact match on owned_product_areas (snake_case strings).
    Fallback pass: if the primary pass finds no candidates, try keyword matching —
    normalise both BU keywords and impact_areas to lowercase space-separated
    tokens, then check equality. This handles the case where SignalScribe uses
    plain-language terms (e.g. "analytics") instead of the registry's exact
    identifiers (e.g. "analytics_portal").

    Recall-biased: prefer over-matching; BUAtlas (gate 4) applies precision.
    Returns BU IDs in registry order.
    """
    impact_areas = set(change_brief.impact_areas)

    # Primary pass: exact string match on owned_product_areas
    candidates: list[str] = []
    for entry in registry.bus:
        owned = set(entry.owned_product_areas)
        if owned & impact_areas:
            candidates.append(entry.bu_id)

    if candidates or not impact_areas:
        return candidates

    # Fallback pass: keyword equality after normalisation
    normed_impact = {_norm(a) for a in impact_areas}
    for entry in registry.bus:
        for kw in entry.keywords:
            if _norm(kw) in normed_impact:
                candidates.append(entry.bu_id)
                break

    return candidates
