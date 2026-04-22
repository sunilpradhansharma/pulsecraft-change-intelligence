"""Unit tests for send_email adapter."""

from __future__ import annotations

import json

import pytest

from pulsecraft.schemas.delivery_payloads import EmailPayload
from pulsecraft.skills.delivery.send_email import send_email
from pulsecraft.skills.delivery.send_teams import (
    DeliveryFailed,
    DeliveryUnauthorized,
)


def _payload() -> EmailPayload:
    return EmailPayload(
        subject="Test subject",
        body_text="Plain text body.",
        body_html="<p>HTML body.</p>",
    )


class TestSendEmail:
    def test_dev_mode_writes_file(self, tmp_path) -> None:
        result = send_email(_payload(), "bu_alpha:head", delivery_root=tmp_path)
        assert result.outcome == "sent"
        assert result.transport_ref is not None
        from pathlib import Path

        assert Path(result.transport_ref).exists()

    def test_dev_mode_file_contains_subject(self, tmp_path) -> None:
        result = send_email(_payload(), "bu_alpha:head", delivery_root=tmp_path)
        from pathlib import Path

        content = json.loads(Path(result.transport_ref).read_text())
        assert content["channel"] == "email"
        assert content["subject"] == "Test subject"

    def test_custom_transport_called(self) -> None:
        called = {}

        def my_transport(payload, recipient):
            called["recipient"] = recipient
            return "smtp-ref-456"

        result = send_email(_payload(), "bu_alpha:head", transport=my_transport)
        assert result.outcome == "sent"
        assert result.transport_ref == "smtp-ref-456"
        assert called["recipient"] == "bu_alpha:head"

    def test_transport_exception_returns_failed(self) -> None:
        def bad(payload, recipient):
            raise RuntimeError("smtp error")

        result = send_email(_payload(), "bu_alpha:head", transport=bad)
        assert result.outcome == "failed"

    def test_delivery_failed_propagates(self) -> None:
        def bad(payload, recipient):
            raise DeliveryFailed("bad address")

        with pytest.raises(DeliveryFailed):
            send_email(_payload(), "bu_alpha:head", transport=bad)

    def test_delivery_unauthorized_propagates(self) -> None:
        def bad(payload, recipient):
            raise DeliveryUnauthorized("expired")

        with pytest.raises(DeliveryUnauthorized):
            send_email(_payload(), "bu_alpha:head", transport=bad)
