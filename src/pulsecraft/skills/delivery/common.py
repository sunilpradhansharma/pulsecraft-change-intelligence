"""Shared rendering helpers for delivery skills."""

from __future__ import annotations

from pathlib import Path

import jinja2

_TEMPLATES_DIR = Path(__file__).parents[4] / "templates"


class RenderingError(Exception):
    """Raised when rendering fails due to template errors or length violations."""


def get_template_env() -> jinja2.Environment:
    """Construct the Jinja2 environment pointed at templates/.

    Autoescape is enabled for .html.j2 templates only (email HTML body).
    All other templates (JSON, plain text, Markdown) use no autoescape.
    UndefinedError is raised immediately on missing variables (StrictUndefined).
    """
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=jinja2.select_autoescape(["html.j2"]),
        undefined=jinja2.StrictUndefined,
    )


def validate_length(payload_str: str, max_bytes: int, channel: str) -> None:
    """Raise RenderingError if payload_str exceeds max_bytes when encoded as UTF-8."""
    actual = len(payload_str.encode("utf-8"))
    if actual > max_bytes:
        raise RenderingError(
            f"{channel} payload too large: {actual} bytes exceeds {max_bytes} byte limit"
        )
