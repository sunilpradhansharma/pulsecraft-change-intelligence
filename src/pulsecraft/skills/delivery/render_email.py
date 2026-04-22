"""Render email (plain-text + HTML) from a PersonalizedBrief."""

from __future__ import annotations

import jinja2

from pulsecraft.schemas.bu_profile import BUProfile
from pulsecraft.schemas.delivery_payloads import EmailPayload
from pulsecraft.schemas.personalized_brief import PersonalizedBrief
from pulsecraft.skills.delivery.common import RenderingError, get_template_env


def render_email(
    personalized_brief: PersonalizedBrief,
    bu_profile: BUProfile,
) -> EmailPayload:
    """Render plain-text and HTML email bodies from the personalized brief.

    Uses email_long variant when present; falls back to teams_medium then push_short.
    Raises RenderingError on missing content or template errors.
    """
    variants = personalized_brief.message_variants
    if variants is None:
        raise RenderingError(
            f"bu={personalized_brief.bu_id}: no message_variants present; cannot render email"
        )

    body = variants.email_long or variants.teams_medium or variants.push_short
    if not body:
        raise RenderingError(
            f"bu={personalized_brief.bu_id}: no email_long, teams_medium, or push_short available"
        )

    subject = f"[PulseCraft] Change notification for {bu_profile.name}"
    recipient_name = bu_profile.head.name

    env = get_template_env()
    ctx = {
        "subject": subject,
        "recipient_name": recipient_name,
        "body": body,
        "recommended_actions": personalized_brief.recommended_actions,
    }

    try:
        body_text = env.get_template("email.txt.j2").render(**ctx)
        body_html = env.get_template("email.html.j2").render(**ctx)
    except jinja2.TemplateError as exc:
        raise RenderingError(f"Email template error: {exc}") from exc

    return EmailPayload(
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )
