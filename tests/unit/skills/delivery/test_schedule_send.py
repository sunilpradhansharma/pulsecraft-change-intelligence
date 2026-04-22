"""Unit tests for schedule_send skill."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from pulsecraft.schemas.delivery_plan import Channel, DeliveryDecision
from pulsecraft.skills.delivery.schedule_send import schedule_send


def _id() -> str:
    return str(uuid.uuid4())


class TestScheduleSend:
    def test_send_now_returns_send_at_equal_to_now(self) -> None:
        now = datetime(2026, 4, 22, 10, 0, tzinfo=UTC)
        result = schedule_send(
            decision=DeliveryDecision.SEND_NOW,
            channel=Channel.TEAMS,
            scheduled_time=None,
            delivery_id=_id(),
            now=now,
        )
        assert result.send_at == now
        assert "SEND_NOW" in result.reason

    def test_hold_until_uses_scheduled_time(self) -> None:
        now = datetime(2026, 4, 22, 10, 0, tzinfo=UTC)
        hold_until = datetime(2026, 4, 22, 20, 0, tzinfo=UTC)
        result = schedule_send(
            decision=DeliveryDecision.HOLD_UNTIL,
            channel=Channel.TEAMS,
            scheduled_time=hold_until,
            delivery_id=_id(),
            now=now,
        )
        assert result.send_at == hold_until
        assert "HOLD_UNTIL" in result.reason

    def test_hold_until_without_scheduled_time_raises(self) -> None:
        with pytest.raises(ValueError, match="scheduled_time"):
            schedule_send(
                decision=DeliveryDecision.HOLD_UNTIL,
                channel=Channel.EMAIL,
                scheduled_time=None,
                delivery_id=_id(),
            )

    def test_digest_computes_next_nine_am_in_recipient_tz(self) -> None:
        # 08:00 UTC = 03:00 America/Chicago — well before 09:00 local
        now_utc = datetime(2026, 4, 22, 8, 0, tzinfo=UTC)
        result = schedule_send(
            decision=DeliveryDecision.DIGEST,
            channel=Channel.EMAIL,
            scheduled_time=None,
            delivery_id=_id(),
            recipient_timezone="America/Chicago",
            now=now_utc,
        )
        # 09:00 America/Chicago on 2026-04-22 = 14:00 UTC (CDT = UTC-5)
        import zoneinfo

        chi = zoneinfo.ZoneInfo("America/Chicago")
        expected = datetime(2026, 4, 22, 9, 0).replace(tzinfo=chi).astimezone(UTC)
        assert abs((result.send_at - expected).total_seconds()) < 60

    def test_digest_past_todays_window_schedules_tomorrow(self) -> None:
        # 15:00 UTC = 10:00 America/Chicago — already past 09:00 local
        now_utc = datetime(2026, 4, 22, 15, 0, tzinfo=UTC)
        result = schedule_send(
            decision=DeliveryDecision.DIGEST,
            channel=Channel.EMAIL,
            scheduled_time=None,
            delivery_id=_id(),
            recipient_timezone="America/Chicago",
            now=now_utc,
        )
        import zoneinfo

        chi = zoneinfo.ZoneInfo("America/Chicago")
        expected = datetime(2026, 4, 23, 9, 0).replace(tzinfo=chi).astimezone(UTC)
        assert abs((result.send_at - expected).total_seconds()) < 60

    def test_escalate_raises(self) -> None:
        with pytest.raises(ValueError, match="ESCALATE"):
            schedule_send(
                decision=DeliveryDecision.ESCALATE,
                channel=None,
                scheduled_time=None,
                delivery_id=_id(),
            )

    def test_send_now_channel_recorded(self) -> None:
        now = datetime(2026, 4, 22, 10, 0, tzinfo=UTC)
        result = schedule_send(
            decision=DeliveryDecision.SEND_NOW,
            channel=Channel.EMAIL,
            scheduled_time=None,
            delivery_id=_id(),
            now=now,
        )
        assert result.channel == "email"

    def test_unknown_timezone_falls_back_to_utc(self) -> None:
        now_utc = datetime(2026, 4, 22, 8, 0, tzinfo=UTC)
        result = schedule_send(
            decision=DeliveryDecision.DIGEST,
            channel=Channel.EMAIL,
            scheduled_time=None,
            delivery_id=_id(),
            recipient_timezone="Not/ATimezone",
            now=now_utc,
        )
        assert result.send_at is not None
