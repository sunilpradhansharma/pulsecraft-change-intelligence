"""Unit tests for send_push adapter."""

from __future__ import annotations

import json

import pytest

from pulsecraft.schemas.delivery_payloads import PushPayload
from pulsecraft.skills.delivery.send_push import send_push
from pulsecraft.skills.delivery.send_teams import (
    DeliveryRetriable,
)


def _payload() -> PushPayload:
    return PushPayload(title="Test title", body="Test body text.")


class TestSendPush:
    def test_dev_mode_writes_file(self, tmp_path) -> None:
        result = send_push(_payload(), "bu_alpha:head", delivery_root=tmp_path)
        assert result.outcome == "sent"
        assert result.transport_ref is not None
        from pathlib import Path

        assert Path(result.transport_ref).exists()

    def test_dev_mode_file_has_push_channel(self, tmp_path) -> None:
        result = send_push(_payload(), "bu_alpha:head", delivery_root=tmp_path)
        from pathlib import Path

        content = json.loads(Path(result.transport_ref).read_text())
        assert content["channel"] == "push"
        assert content["title"] == "Test title"

    def test_custom_transport_receives_payload(self) -> None:
        received = {}

        def my_transport(payload, recipient):
            received["title"] = payload.title
            return "push-token-789"

        result = send_push(_payload(), "bu_alpha:head", transport=my_transport)
        assert result.outcome == "sent"
        assert received["title"] == "Test title"

    def test_transport_exception_returns_failed(self) -> None:
        def bad(payload, recipient):
            raise RuntimeError("push service down")

        result = send_push(_payload(), "bu_alpha:head", transport=bad)
        assert result.outcome == "failed"
        assert "push service down" in (result.error_reason or "")

    def test_delivery_retriable_propagates(self) -> None:
        def bad(payload, recipient):
            raise DeliveryRetriable("rate limited")

        with pytest.raises(DeliveryRetriable):
            send_push(_payload(), "bu_alpha:head", transport=bad)
