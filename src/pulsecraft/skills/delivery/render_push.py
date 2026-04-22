"""Render a short push notification from a PersonalizedBrief."""

from __future__ import annotations

import jinja2

from pulsecraft.schemas.bu_profile import BUProfile
from pulsecraft.schemas.delivery_payloads import PushPayload
from pulsecraft.schemas.personalized_brief import PersonalizedBrief
from pulsecraft.skills.delivery.common import RenderingError, get_template_env

_TITLE_MAX = 65
_BODY_MAX = 240


def render_push(
    personalized_brief: PersonalizedBrief,
    bu_profile: BUProfile,
) -> PushPayload:
    """Render a short push notification from the personalized brief.

    Uses push_short variant. Title capped at 65 chars, body at 240 chars.
    Raises RenderingError on missing content or template errors.
    """
    variants = personalized_brief.message_variants
    if variants is None:
        raise RenderingError(
            f"bu={personalized_brief.bu_id}: no message_variants present; cannot render push"
        )

    body_text = variants.push_short
    if not body_text:
        raise RenderingError(f"bu={personalized_brief.bu_id}: no push_short variant available")

    title_raw = f"[PulseCraft] {bu_profile.name}"
    title = title_raw[:_TITLE_MAX]

    env = get_template_env()
    try:
        rendered = env.get_template("push.j2").render(
            title=title,
            body=body_text,
        )
    except jinja2.TemplateError as exc:
        raise RenderingError(f"Push template error: {exc}") from exc

    lines = rendered.strip().splitlines()
    rendered_title = lines[0][:_TITLE_MAX] if lines else title
    rendered_body = lines[1][:_BODY_MAX] if len(lines) > 1 else body_text[:_BODY_MAX]

    return PushPayload(title=rendered_title, body=rendered_body)
