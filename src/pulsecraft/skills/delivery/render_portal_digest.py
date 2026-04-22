"""Render a portal digest Markdown document from a list of PersonalizedBriefs."""

from __future__ import annotations

from datetime import UTC, datetime

import jinja2

from pulsecraft.schemas.bu_profile import BUProfile
from pulsecraft.schemas.delivery_payloads import DigestPayload
from pulsecraft.schemas.personalized_brief import PersonalizedBrief
from pulsecraft.skills.delivery.common import RenderingError, get_template_env


def render_portal_digest(
    personalized_briefs: list[PersonalizedBrief],
    bu_profile: BUProfile,
    digest_date: datetime | None = None,
) -> DigestPayload:
    """Render a combined digest Markdown document from multiple PersonalizedBriefs.

    Each brief becomes one item in the digest. Returns a DigestPayload with combined
    Markdown suitable for portal delivery. Raises RenderingError on template errors.
    """
    if digest_date is None:
        digest_date = datetime.now(UTC)

    items = []
    for pb in personalized_briefs:
        title = f"Change notification for {bu_profile.name}"
        if pb.why_relevant:
            snippet = pb.why_relevant
        elif pb.message_variants and pb.message_variants.push_short:
            snippet = pb.message_variants.push_short
        else:
            snippet = "A relevant change has been detected."
        items.append(
            {
                "title": title,
                "why_relevant": snippet,
                "recommended_actions": pb.recommended_actions,
            }
        )

    env = get_template_env()
    try:
        rendered = env.get_template("portal_digest.md.j2").render(
            digest_date=digest_date.strftime("%Y-%m-%d"),
            bu_name=bu_profile.name,
            items=items,
            item_count=len(items),
        )
    except jinja2.TemplateError as exc:
        raise RenderingError(f"Portal digest template error: {exc}") from exc

    return DigestPayload(
        markdown=rendered,
        item_count=len(items),
        bu_id=bu_profile.bu_id,
        digest_date=digest_date.date(),
    )
