from datetime import UTC, datetime
from pathlib import Path

import pytest

from pig_finserv.audit import AuditEventInput, AuditIntegrityError, AuditStore
from pig_finserv.domain import MaskingStatus, TriageAction


def _payload(action: TriageAction = TriageAction.AUTO_ROUTE) -> AuditEventInput:
    return AuditEventInput(
        action=action,
        reason_code="POLICY_ELIGIBLE",
        masking_status=MaskingStatus.MASKED,
        masked_entity_counts={"EMAIL": 1},
        input_fingerprint="a" * 64,
        model_version="product-v1",
        taxonomy_version="2026.1",
        threshold_policy_version="cost-1-10-v1",
        predicted_product="Credit card",
        confidence=0.93,
    )


def test_audit_store_appends_and_verifies_hash_chain(tmp_path: Path) -> None:
    store = AuditStore(tmp_path / "audit.sqlite")

    first = store.append(_payload(), occurred_at=datetime(2026, 11, 1, tzinfo=UTC))
    second = store.append(
        _payload(TriageAction.HUMAN_REVIEW_LOW_CONFIDENCE),
        occurred_at=datetime(2026, 11, 2, tzinfo=UTC),
    )

    assert first.event_sequence == 1
    assert first.previous_event_hash is None
    assert second.event_sequence == 2
    assert second.previous_event_hash == first.event_hash
    assert store.verify_integrity() == 2


def test_audit_store_detects_direct_payload_tampering(tmp_path: Path) -> None:
    store = AuditStore(tmp_path / "audit.sqlite")
    store.append(_payload(), occurred_at=datetime(2026, 11, 1, tzinfo=UTC))

    with store._connection() as connection:  # noqa: SLF001 - deliberate integrity attack fixture
        connection.execute("UPDATE audit_events SET payload_json = '{}' WHERE event_sequence = 1")

    with pytest.raises(AuditIntegrityError, match="hash mismatch"):
        store.verify_integrity()
