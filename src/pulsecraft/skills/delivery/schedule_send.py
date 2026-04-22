"""Compute when a delivery should go out based on its decision."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pulsecraft.schemas.delivery_payloads import ScheduledDelivery
from pulsecraft.schemas.delivery_plan import Channel, DeliveryDecision


def schedule_send(
    decision: DeliveryDecision,
    channel: Channel | None,
    scheduled_time: datetime | None,
    delivery_id: str,
    recipient_timezone: str = "UTC",
    now: datetime | None = None,
) -> ScheduledDelivery:
    """Compute when a delivery should go out based on its decision type.

    SEND_NOW  → send_at = now (immediate)
    HOLD_UNTIL → send_at = scheduled_time (provided by PushPilot)
    DIGEST    → send_at = next occurrence of digest.send_time_recipient_local in recipient tz
    ESCALATE  → raises ValueError; callers must intercept escalate before reaching here
    """
    if now is None:
        now = datetime.now(UTC)

    channel_str = str(channel) if channel else "unspecified"

    if decision == DeliveryDecision.ESCALATE:
        raise ValueError("schedule_send called with ESCALATE decision; route to HITL instead")

    if decision == DeliveryDecision.SEND_NOW:
        return ScheduledDelivery(
            delivery_id=delivery_id,
            send_at=now,
            channel=channel_str,
            reason="SEND_NOW: deliver immediately",
        )

    if decision == DeliveryDecision.HOLD_UNTIL:
        if scheduled_time is None:
            raise ValueError("HOLD_UNTIL decision requires scheduled_time to be non-None")
        return ScheduledDelivery(
            delivery_id=delivery_id,
            send_at=scheduled_time,
            channel=channel_str,
            reason=f"HOLD_UNTIL: defer to {scheduled_time.isoformat()}",
        )

    # DIGEST: compute next occurrence of configured send_time in recipient's timezone.
    # Read from channel_policy.yaml; fall back to "09:00" if config unavailable.
    send_time_str = _load_digest_send_time()

    tz_info: ZoneInfo | timezone
    try:
        tz_info = ZoneInfo(recipient_timezone)
    except ZoneInfoNotFoundError:
        tz_info = UTC
    tz = tz_info

    sh, sm = map(int, send_time_str.split(":"))
    now_local = now.astimezone(tz)
    today = now_local.date()

    candidate_naive = datetime(today.year, today.month, today.day, sh, sm)
    candidate_local = candidate_naive.replace(tzinfo=tz)

    if now_local >= candidate_local:
        tomorrow = today + timedelta(days=1)
        candidate_naive = datetime(tomorrow.year, tomorrow.month, tomorrow.day, sh, sm)
        candidate_local = candidate_naive.replace(tzinfo=tz)

    send_at_utc = candidate_local.astimezone(UTC)

    return ScheduledDelivery(
        delivery_id=delivery_id,
        send_at=send_at_utc,
        channel=channel_str,
        reason=f"DIGEST: next digest window at {send_time_str} {recipient_timezone}",
    )


def _load_digest_send_time() -> str:
    """Return digest send time from channel_policy.yaml, defaulting to '09:00'."""
    try:
        from pulsecraft.config.loader import get_channel_policy

        return get_channel_policy().digest.send_time_recipient_local
    except Exception:
        return "09:00"
