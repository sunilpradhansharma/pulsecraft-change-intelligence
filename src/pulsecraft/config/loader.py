"""Config loader — reads and validates YAML config files; caches in-memory."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, TypeVar, cast

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from pulsecraft.schemas.bu_profile import BUProfile
from pulsecraft.schemas.bu_registry import BURegistry
from pulsecraft.schemas.channel_policy import ChannelPolicy
from pulsecraft.schemas.policy import Policy

T = TypeVar("T", bound=BaseModel)


class ConfigValidationError(Exception):
    """Raised when a config file fails Pydantic schema validation."""


class _BUProfilesFile(BaseModel):
    """File-level wrapper for bu_profiles.yaml (schema_version + profiles list)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    profiles: list[BUProfile]


# Module-level cache; cleared by reload_config() for test isolation.
_CACHE: dict[str, Any] = {}


def reload_config() -> None:
    """Clear the in-memory config cache, forcing fresh reads on next access."""
    _CACHE.clear()


def _config_dir() -> Path:
    """Resolve the config directory from PULSECRAFT_CONFIG_DIR env var (default: ./config)."""
    raw = os.environ.get("PULSECRAFT_CONFIG_DIR", "./config")
    return Path(raw)


def _load_yaml(filename: str) -> Any:
    path = _config_dir() / filename
    try:
        with path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except FileNotFoundError:
        raise ConfigValidationError(f"Config file not found: {path}") from None
    except yaml.YAMLError as exc:
        raise ConfigValidationError(f"YAML parse error in {path}: {exc}") from exc


def _parse(model_cls: type[T], data: Any, filename: str) -> T:
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise ConfigValidationError(f"Validation failed for {filename}:\n{exc}") from exc


def get_bu_registry() -> BURegistry:
    """Return the validated BU registry, loading from bu_registry.yaml if not cached."""
    if "bu_registry" not in _CACHE:
        data = _load_yaml("bu_registry.yaml")
        _CACHE["bu_registry"] = _parse(BURegistry, data, "bu_registry.yaml")
    return cast(BURegistry, _CACHE["bu_registry"])


def _load_profiles_file() -> _BUProfilesFile:
    """Load and cache bu_profiles.yaml."""
    if "bu_profiles" not in _CACHE:
        data = _load_yaml("bu_profiles.yaml")
        _CACHE["bu_profiles"] = _parse(_BUProfilesFile, data, "bu_profiles.yaml")
    return cast(_BUProfilesFile, _CACHE["bu_profiles"])


def get_bu_profile(bu_id: str) -> BUProfile:
    """Return the BUProfile for bu_id; raises KeyError if the BU is not registered."""
    by_id = {p.bu_id: p for p in _load_profiles_file().profiles}
    if bu_id not in by_id:
        raise KeyError(f"No BU profile found for bu_id={bu_id!r}")
    return by_id[bu_id]


def get_policy() -> Policy:
    """Return the validated Policy config, loading from policy.yaml if not cached."""
    if "policy" not in _CACHE:
        data = _load_yaml("policy.yaml")
        _CACHE["policy"] = _parse(Policy, data, "policy.yaml")
    return cast(Policy, _CACHE["policy"])


def get_channel_policy() -> ChannelPolicy:
    """Return the validated ChannelPolicy config, loading from channel_policy.yaml if not cached."""
    if "channel_policy" not in _CACHE:
        data = _load_yaml("channel_policy.yaml")
        _CACHE["channel_policy"] = _parse(ChannelPolicy, data, "channel_policy.yaml")
    return cast(ChannelPolicy, _CACHE["channel_policy"])
