"""Each config file loads and validates via the loader without error."""

from __future__ import annotations

from pulsecraft.config import (
    get_bu_registry,
    get_channel_policy,
    get_policy,
)
from pulsecraft.config.loader import _load_profiles_file
from pulsecraft.schemas.bu_profile import BUProfile
from pulsecraft.schemas.bu_registry import BURegistry
from pulsecraft.schemas.channel_policy import ChannelPolicy
from pulsecraft.schemas.policy import Policy


def test_bu_registry_loads() -> None:
    registry = get_bu_registry()
    assert isinstance(registry, BURegistry)
    assert len(registry.bus) >= 1


def test_bu_registry_has_six_bus() -> None:
    assert len(get_bu_registry().bus) == 6


def test_bu_registry_bu_ids_are_unique() -> None:
    ids = [entry.bu_id for entry in get_bu_registry().bus]
    assert len(ids) == len(set(ids)), "Duplicate bu_id values in bu_registry.yaml"


def test_bu_profiles_file_loads() -> None:
    profiles_file = _load_profiles_file()
    assert len(profiles_file.profiles) >= 1


def test_bu_profiles_has_six_profiles() -> None:
    assert len(_load_profiles_file().profiles) == 6


def test_bu_profiles_are_bu_profile_instances() -> None:
    for profile in _load_profiles_file().profiles:
        assert isinstance(profile, BUProfile)


def test_policy_loads() -> None:
    policy = get_policy()
    assert isinstance(policy, Policy)


def test_channel_policy_loads() -> None:
    cp = get_channel_policy()
    assert isinstance(cp, ChannelPolicy)


def test_reload_config_clears_cache() -> None:
    from pulsecraft.config.loader import _CACHE, reload_config

    get_bu_registry()
    assert "bu_registry" in _CACHE
    reload_config()
    assert "bu_registry" not in _CACHE
