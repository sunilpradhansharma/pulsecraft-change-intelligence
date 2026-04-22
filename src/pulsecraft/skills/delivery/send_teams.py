"""Send a Teams adaptive card. Dev-mode writes to audit/deliveries/; real transport injectable."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pulsecraft.schemas.delivery_payloads import DeliveryResult, TeamsCardPayload

_DEFAULT_DELIVERY_ROOT = Path("audit/deliveries")


class DeliveryFailed(Exception):
    """Permanent delivery failure — bad address, unauthorized tenant. No retry."""


class DeliveryRetriable(Exception):
    """Transient delivery failure — rate limit, timeout, 5xx. Caller may retry."""


class DeliveryUnauthorized(Exception):
    """Auth problem — OAuth token expired, wrong tenant. Caller escalates to HITL."""


def send_teams(
    payload: TeamsCardPayload,
    recipient: str,
    transport: Callable[[TeamsCardPayload, str], str] | None = None,
    delivery_root: Path | None = None,
) -> DeliveryResult:
    """Send a Teams adaptive card to a recipient.

    Dev mode (transport=None): writes payload JSON to audit/deliveries/<date>/<id>.json
    and returns DeliveryResult with outcome='sent'.

    Production mode: calls transport(payload, recipient) → transport_ref string.
    Maps exceptions to DeliveryFailed / DeliveryRetriable / DeliveryUnauthorized.
    """
    delivery_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    if transport is None:
        root = delivery_root or _DEFAULT_DELIVERY_ROOT
        date_dir = root / now.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        file_path = date_dir / f"{delivery_id}.json"
        file_path.write_text(
            json.dumps(
                {
                    "channel": "teams",
                    "recipient": recipient,
                    "delivery_id": delivery_id,
                    "sent_at": now.isoformat(),
                    "payload": payload.card_json,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return DeliveryResult(
            delivery_id=delivery_id,
            outcome="sent",
            transport_ref=str(file_path),
            sent_at=now,
        )

    try:
        transport_ref = transport(payload, recipient)
        return DeliveryResult(
            delivery_id=delivery_id,
            outcome="sent",
            transport_ref=str(transport_ref) if transport_ref is not None else None,
            sent_at=now,
        )
    except DeliveryUnauthorized:
        raise
    except DeliveryFailed:
        raise
    except DeliveryRetriable:
        raise
    except Exception as exc:
        return DeliveryResult(
            delivery_id=delivery_id,
            outcome="failed",
            error_reason=str(exc)[:400],
        )
