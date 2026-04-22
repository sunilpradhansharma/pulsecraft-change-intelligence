"""Config test fixtures: point PULSECRAFT_CONFIG_DIR at the real config/ directory."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[3]
CONFIG_DIR = REPO_ROOT / "config"


@pytest.fixture(autouse=True)
def set_config_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin PULSECRAFT_CONFIG_DIR to the repo config/ directory and clear the cache."""
    monkeypatch.setenv("PULSECRAFT_CONFIG_DIR", str(CONFIG_DIR))
    from pulsecraft.config.loader import reload_config

    reload_config()
    yield
    reload_config()
