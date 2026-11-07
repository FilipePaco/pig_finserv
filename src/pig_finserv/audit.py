"""Append-only, hash-chained local audit events for triage decisions."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pig_finserv.domain import MaskingStatus, ReviewOutcome, TriageAction


class AuditIntegrityError(RuntimeError):
    """Raised when an audit hash chain is missing or no longer valid."""


@dataclass(frozen=True, slots=True)
class AuditEventInput:
    """Safe, minimized input required to persist a triage audit event."""

    action: TriageAction
    reason_code: str
    masking_status: MaskingStatus
    masked_entity_counts: dict[str, int]
    input_fingerprint: str | None = None
    request_id: str | None = None
    model_version: str | None = None
    taxonomy_version: str | None = None
    threshold_policy_version: str | None = None
    predicted_product: str | None = None
    confidence: float | None = None
    parent_audit_id: str | None = None
    review_correction: dict[str, str | None] | None = None


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Persisted event including application-level hash-chain metadata."""

    audit_id: str
    occurred_at: str
    event_sequence: int
    previous_event_hash: str | None
    event_hash: str
    payload: AuditEventInput


class AuditStore:
    """SQLite event store with application-enforced append semantics."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def append(
        self, payload: AuditEventInput, *, occurred_at: datetime | None = None
    ) -> AuditEvent:
        """Append a safe event and atomically link it to the previous event hash."""

        _validate_payload(payload)
        source_time = occurred_at or datetime.now(UTC)
        if source_time.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        occurred = source_time.astimezone(UTC)
        serialized_payload = _canonical_payload(payload)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            last = connection.execute(
                "SELECT event_sequence, event_hash "
                "FROM audit_events ORDER BY event_sequence DESC LIMIT 1"
            ).fetchone()
            sequence = (last[0] if last else 0) + 1
            previous_hash = last[1] if last else None
            audit_id = f"triage_{uuid4()}"
            occurred_at = occurred.isoformat()
            event_hash = _event_hash(
                audit_id=audit_id,
                occurred_at=occurred_at,
                event_sequence=sequence,
                previous_event_hash=previous_hash,
                serialized_payload=serialized_payload,
            )
            connection.execute(
                """
                INSERT INTO audit_events (
                    audit_id, occurred_at, event_sequence, previous_event_hash,
                    event_hash, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (audit_id, occurred_at, sequence, previous_hash, event_hash, serialized_payload),
            )
        return AuditEvent(
            audit_id=audit_id,
            occurred_at=occurred_at,
            event_sequence=sequence,
            previous_event_hash=previous_hash,
            event_hash=event_hash,
            payload=payload,
        )

    def verify_integrity(self) -> int:
        """Verify event ordering and hashes; return the verified event count."""

        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT audit_id, occurred_at, event_sequence, previous_event_hash,
                       event_hash, payload_json
                FROM audit_events ORDER BY event_sequence
                """
            ).fetchall()
        previous_hash: str | None = None
        for expected_sequence, row in enumerate(rows, start=1):
            audit_id, occurred_at, sequence, stored_previous, stored_hash, payload_json = row
            if sequence != expected_sequence or stored_previous != previous_hash:
                raise AuditIntegrityError(f"audit sequence mismatch at event {audit_id}")
            expected_hash = _event_hash(
                audit_id=audit_id,
                occurred_at=occurred_at,
                event_sequence=sequence,
                previous_event_hash=stored_previous,
                serialized_payload=payload_json,
            )
            if stored_hash != expected_hash:
                raise AuditIntegrityError(f"audit hash mismatch at event {audit_id}")
            previous_hash = stored_hash
        return len(rows)

    def sanitized_event(self, audit_id: str) -> dict[str, object] | None:
        """Return an operator-safe event view without fingerprints or raw text."""

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT audit_id, occurred_at, event_sequence, previous_event_hash,
                       event_hash, payload_json
                FROM audit_events WHERE audit_id = ?
                """,
                [audit_id],
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row[5])
        payload.pop("input_fingerprint", None)
        payload.pop("request_id", None)
        return {
            "audit_id": row[0],
            "occurred_at": row[1],
            "event_sequence": row[2],
            "previous_event_hash": row[3],
            "event_hash": row[4],
            "payload": payload,
        }

    def append_review(
        self,
        *,
        parent_audit_id: str,
        corrected_product: str,
        corrected_issue: str | None,
        outcome: ReviewOutcome,
        reason_code: str,
    ) -> AuditEvent:
        """Append a canonical human correction without overwriting the prediction."""

        if not self.sanitized_event(parent_audit_id):
            raise ValueError("parent audit event was not found")
        if not corrected_product.strip():
            raise ValueError("corrected_product must not be blank")
        if corrected_issue is not None and not corrected_issue.strip():
            raise ValueError("corrected_issue must be omitted or non-blank")
        return self.append(
            AuditEventInput(
                action=TriageAction.HUMAN_REVIEW_LOW_CONFIDENCE,
                reason_code=reason_code,
                masking_status=MaskingStatus.NOT_REQUIRED,
                masked_entity_counts={},
                parent_audit_id=parent_audit_id,
                review_correction={
                    "corrected_product": corrected_product.strip(),
                    "corrected_issue": corrected_issue.strip() if corrected_issue else None,
                    "outcome": outcome.value,
                },
            )
        )

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    audit_id TEXT PRIMARY KEY,
                    occurred_at TEXT NOT NULL,
                    event_sequence INTEGER NOT NULL UNIQUE,
                    previous_event_hash TEXT,
                    event_hash TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL
                )
                """
            )

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _canonical_payload(payload: AuditEventInput) -> str:
    values = asdict(payload)
    values["action"] = payload.action.value
    values["masking_status"] = payload.masking_status.value
    values["masked_entity_counts"] = dict(sorted(payload.masked_entity_counts.items()))
    return json.dumps(values, sort_keys=True, separators=(",", ":"))


def _validate_payload(payload: AuditEventInput) -> None:
    """Reject caller-controlled metadata that could become unmasked free text."""

    if payload.request_id is not None:
        try:
            UUID(payload.request_id)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("request_id must be an opaque UUID") from exc
    if not payload.reason_code or not payload.reason_code.replace("_", "").isalnum():
        raise ValueError("reason_code must be an allowlisted uppercase-style token")
    if payload.reason_code != payload.reason_code.upper() or len(payload.reason_code) > 64:
        raise ValueError("reason_code must be an allowlisted uppercase-style token")


def _event_hash(
    *,
    audit_id: str,
    occurred_at: str,
    event_sequence: int,
    previous_event_hash: str | None,
    serialized_payload: str,
) -> str:
    material = json.dumps(
        {
            "audit_id": audit_id,
            "event_sequence": event_sequence,
            "occurred_at": occurred_at,
            "payload": json.loads(serialized_payload),
            "previous_event_hash": previous_event_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode()).hexdigest()
