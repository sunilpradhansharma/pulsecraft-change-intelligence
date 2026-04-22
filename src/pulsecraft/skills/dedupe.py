"""Dedupe skill — deterministic key computation and duplicate detection."""

from __future__ import annotations

import hashlib
import json

from pulsecraft.orchestrator.audit import AuditReader
from pulsecraft.schemas.audit_record import EventType


def compute_dedupe_key(
    change_id: str,
    bu_id: str,
    recipient_id: str,
    message_variant_id: str,
) -> str:
    """Return a deterministic SHA-256 hex string for the four input identifiers.

    Stable across replays: same inputs always produce the same key.
    """
    data = {
        "change_id": change_id,
        "bu_id": bu_id,
        "recipient_id": recipient_id,
        "message_variant_id": message_variant_id,
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def has_recent_duplicate(
    dedupe_key: str,
    audit_reader: AuditReader,
    window_hours: int,
) -> bool:
    """Return True if a delivery_attempt record with dedupe_key == dedupe_key exists in window.

    Scans all DELIVERY_ATTEMPT records in the audit log within the last window_hours.
    Matches against AuditRecord.dedupe_key (not input_hash). Delivery records must be
    written by _write_delivery with the dedupe_key field populated for this to work.
    """
    records = audit_reader.read_recent_events(EventType.DELIVERY_ATTEMPT, window_hours)
    return any(r.dedupe_key == dedupe_key for r in records)
