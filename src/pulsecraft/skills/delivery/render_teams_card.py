"""Render a Teams adaptive card from a PersonalizedBrief."""

from __future__ import annotations

import json

import jinja2

from pulsecraft.schemas.bu_profile import BUProfile
from pulsecraft.schemas.delivery_payloads import TeamsCardPayload
from pulsecraft.schemas.personalized_brief import PersonalizedBrief
from pulsecraft.skills.delivery.common import RenderingError, get_template_env

_TEAMS_MAX_BYTES = 28 * 1024  # 28 KB per Teams adaptive card docs


def render_teams_card(
    personalized_brief: PersonalizedBrief,
    bu_profile: BUProfile,
) -> TeamsCardPayload:
    """Render a Teams adaptive card from the personalized brief.

    Uses teams_medium variant; falls back to push_short if teams_medium is absent.
    Raises RenderingError on missing content, template errors, or size overflow.
    """
    variants = personalized_brief.message_variants
    if variants is None:
        raise RenderingError(
            f"bu={personalized_brief.bu_id}: no message_variants present; cannot render Teams card"
        )

    body = variants.teams_medium or variants.push_short
    if not body:
        raise RenderingError(
            f"bu={personalized_brief.bu_id}: no teams_medium or push_short variant available"
        )

    env = get_template_env()
    try:
        tmpl = env.get_template("teams_card.j2")
        rendered = tmpl.render(
            title=f"[PulseCraft] {bu_profile.name}",
            body=body,
            why_relevant=personalized_brief.why_relevant,
            recommended_actions=personalized_brief.recommended_actions,
        )
    except jinja2.TemplateError as exc:
        raise RenderingError(f"Teams card template error: {exc}") from exc

    try:
        card_dict = json.loads(rendered)
    except json.JSONDecodeError as exc:
        raise RenderingError(f"Teams card template produced invalid JSON: {exc}") from exc

    card_str = json.dumps(card_dict, ensure_ascii=False)
    length_bytes = len(card_str.encode("utf-8"))
    if length_bytes > _TEAMS_MAX_BYTES:
        raise RenderingError(
            f"Teams card too large: {length_bytes} bytes exceeds {_TEAMS_MAX_BYTES} byte limit"
        )

    return TeamsCardPayload(card_json=card_dict, length_bytes=length_bytes)
