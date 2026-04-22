"""Shared setup for all integration tests — loads .env so ANTHROPIC_API_KEY is available."""

from __future__ import annotations

import os
from pathlib import Path


def _load_env() -> None:
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


_load_env()
