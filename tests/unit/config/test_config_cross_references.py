"""Cross-reference integrity: registry ↔ profiles and therapeutic area vocabulary."""

from __future__ import annotations

from pulsecraft.config import get_bu_registry
from pulsecraft.config.loader import _load_profiles_file

KNOWN_THERAPEUTIC_AREAS = {
    "immunology",
    "oncology",
    "neuroscience",
    "hematology",
    "dermatology",
    "gastroenterology",
    "rheumatology",
    "aesthetics",
}


def test_every_profile_bu_id_is_in_registry() -> None:
    """Every BU in bu_profiles.yaml has a matching entry in bu_registry.yaml."""
    registry_ids = {entry.bu_id for entry in get_bu_registry().bus}
    for profile in _load_profiles_file().profiles:
        assert profile.bu_id in registry_ids, (
            f"Profile bu_id={profile.bu_id!r} has no matching entry in bu_registry.yaml"
        )


def test_every_registry_entry_has_a_profile() -> None:
    """Every BU in bu_registry.yaml has a matching profile in bu_profiles.yaml."""
    profile_ids = {p.bu_id for p in _load_profiles_file().profiles}
    for entry in get_bu_registry().bus:
        assert entry.bu_id in profile_ids, (
            f"Registry entry bu_id={entry.bu_id!r} has no matching profile in bu_profiles.yaml"
        )


def test_registry_and_profiles_owned_areas_agree() -> None:
    """owned_product_areas in registry and profile must match for each BU."""
    registry_by_id = {e.bu_id: e for e in get_bu_registry().bus}
    for profile in _load_profiles_file().profiles:
        registry_entry = registry_by_id[profile.bu_id]
        assert set(profile.owned_product_areas) == set(registry_entry.owned_product_areas), (
            f"owned_product_areas mismatch for bu_id={profile.bu_id!r}: "
            f"registry={registry_entry.owned_product_areas}, "
            f"profile={profile.owned_product_areas}"
        )


def test_therapeutic_areas_are_from_known_set_or_null() -> None:
    """All therapeutic_area values are either null or in the known vocabulary."""
    for entry in get_bu_registry().bus:
        if entry.therapeutic_area is not None:
            assert entry.therapeutic_area in KNOWN_THERAPEUTIC_AREAS, (
                f"bu_id={entry.bu_id!r} has unknown therapeutic_area={entry.therapeutic_area!r}. "
                f"Known: {sorted(KNOWN_THERAPEUTIC_AREAS)}"
            )
    for profile in _load_profiles_file().profiles:
        if profile.therapeutic_area is not None:
            assert profile.therapeutic_area in KNOWN_THERAPEUTIC_AREAS, (
                f"Profile bu_id={profile.bu_id!r} has unknown "
                f"therapeutic_area={profile.therapeutic_area!r}"
            )
