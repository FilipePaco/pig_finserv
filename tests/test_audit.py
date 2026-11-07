from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from pig_finserv.audit import AuditEventInput, AuditIntegrityError, AuditStore
from pig_finserv.domain import MaskingStatus, ReviewOutcome, TriageAction


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


def test_audit_store_rejects_free_text_metadata(tmp_path: Path) -> None:
    payload = AuditEventInput(
        action=TriageAction.REJECTED_INVALID_REQUEST,
        reason_code="consumer email is jane@example.com",
        masking_status=MaskingStatus.NOT_RUN,
        masked_entity_counts={},
        request_id="not-a-uuid",
    )

    with pytest.raises(ValueError, match="request_id"):
        AuditStore(tmp_path / "audit.sqlite").append(payload)


def test_sanitized_event_omits_fingerprint_and_caller_request_id(tmp_path: Path) -> None:
    store = AuditStore(tmp_path / "audit.sqlite")
    event = store.append(
        replace(_payload(), request_id="81b900c1-b755-442c-a0b3-b0967009e412")
    )

    sanitized = store.sanitized_event(event.audit_id)

    assert sanitized is not None
    assert "input_fingerprint" not in sanitized["payload"]
    assert "request_id" not in sanitized["payload"]


def test_review_appends_correction_without_mutating_original_event(tmp_path: Path) -> None:
    store = AuditStore(tmp_path / "audit.sqlite")
    original = store.append(_payload())

    correction = store.append_review(
        parent_audit_id=original.audit_id,
        corrected_product="Mortgage",
        corrected_issue=None,
        outcome=ReviewOutcome.CORRECTED,
        reason_code="OPERATOR_CORRECTION",
    )

    original_view = store.sanitized_event(original.audit_id)
    correction_view = store.sanitized_event(correction.audit_id)
    assert original_view is not None
    assert correction_view is not None
    assert original_view["payload"]["review_correction"] is None
    assert correction_view["payload"]["parent_audit_id"] == original.audit_id
    assert correction_view["payload"]["review_correction"]["corrected_product"] == "Mortgage"
    assert store.verify_integrity() == 2
