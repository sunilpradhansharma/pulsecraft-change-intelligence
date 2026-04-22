"""Unit tests for send_teams adapter."""

from __future__ import annotations

import json

import pytest

from pulsecraft.schemas.delivery_payloads import TeamsCardPayload
from pulsecraft.skills.delivery.send_teams import (
    DeliveryFailed,
    DeliveryRetriable,
    DeliveryUnauthorized,
    send_teams,
)


def _payload() -> TeamsCardPayload:
    card = {"type": "AdaptiveCard", "version": "1.5", "body": []}
    return TeamsCardPayload(card_json=card, length_bytes=len(json.dumps(card)))


class TestSendTeams:
    def test_dev_mode_writes_file(self, tmp_path) -> None:
        result = send_teams(_payload(), "bu_alpha:head", delivery_root=tmp_path)
        assert result.outcome == "sent"
        assert result.transport_ref is not None
        assert result.sent_at is not None
        from pathlib import Path

        assert Path(result.transport_ref).exists()

    def test_dev_mode_file_contains_payload(self, tmp_path) -> None:
        result = send_teams(_payload(), "bu_alpha:head", delivery_root=tmp_path)
        from pathlib import Path

        content = json.loads(Path(result.transport_ref).read_text())
        assert content["channel"] == "teams"
        assert content["recipient"] == "bu_alpha:head"
        assert "payload" in content

    def test_custom_transport_receives_payload_and_recipient(self) -> None:
        received = {}

        def my_transport(payload, recipient):
            received["payload"] = payload
            received["recipient"] = recipient
            return "msg-123"

        result = send_teams(_payload(), "bu_alpha:head", transport=my_transport)
        assert result.outcome == "sent"
        assert result.transport_ref == "msg-123"
        assert received["recipient"] == "bu_alpha:head"

    def test_transport_exception_returns_failed_result(self) -> None:
        def bad_transport(payload, recipient):
            raise RuntimeError("network timeout")

        result = send_teams(_payload(), "bu_alpha:head", transport=bad_transport)
        assert result.outcome == "failed"
        assert result.error_reason is not None
        assert "network timeout" in result.error_reason

    def test_delivery_failed_propagates(self) -> None:
        def bad_transport(payload, recipient):
            raise DeliveryFailed("bad address")

        with pytest.raises(DeliveryFailed):
            send_teams(_payload(), "bu_alpha:head", transport=bad_transport)

    def test_delivery_unauthorized_propagates(self) -> None:
        def bad_transport(payload, recipient):
            raise DeliveryUnauthorized("token expired")

        with pytest.raises(DeliveryUnauthorized):
            send_teams(_payload(), "bu_alpha:head", transport=bad_transport)

    def test_delivery_retriable_propagates(self) -> None:
        def bad_transport(payload, recipient):
            raise DeliveryRetriable("rate limited")

        with pytest.raises(DeliveryRetriable):
            send_teams(_payload(), "bu_alpha:head", transport=bad_transport)
