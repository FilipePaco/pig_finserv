"""Explicit safe triage workflow: mask, predict, policy, audit, and return."""

from __future__ import annotations

from dataclasses import dataclass

from pig_finserv.audit import AuditEventInput, AuditStore
from pig_finserv.domain import MaskingStatus, TriageAction, TriageRequest
from pig_finserv.modeling.baseline import TfidfLogisticProductClassifier
from pig_finserv.modeling.policy import ThresholdPolicy
from pig_finserv.safety.pii import PiiMasker, PiiMaskingError


@dataclass(frozen=True, slots=True)
class TriageResult:
    audit_id: str
    action: TriageAction
    predicted_product: str | None
    confidence: float | None
    guardrail_status: MaskingStatus
    reason_code: str


class TriageService:
    """Run the fixed triage state machine without external model/tool access."""

    def __init__(
        self,
        *,
        masker: PiiMasker,
        classifier: TfidfLogisticProductClassifier,
        policy: ThresholdPolicy,
        class_calibration_support: dict[str, int],
        audit_store: AuditStore,
        probabilities_calibrated: bool,
    ) -> None:
        self._masker = masker
        self._classifier = classifier
        self._policy = policy
        self._class_calibration_support = class_calibration_support
        self._audit_store = audit_store
        self._probabilities_calibrated = probabilities_calibrated

    def triage(self, request: TriageRequest) -> TriageResult:
        """Return a safe route suggestion or human-review outcome with an audit ID."""

        if not request.has_usable_narrative():
            return self._audit_result(
                action=TriageAction.HUMAN_REVIEW_EMPTY_INPUT,
                reason_code="EMPTY_NARRATIVE",
                masking_status=MaskingStatus.NOT_RUN,
            )
        try:
            masked = self._masker.mask(request.narrative)
        except PiiMaskingError:
            return self._audit_result(
                action=TriageAction.HUMAN_REVIEW_GUARDRAIL_FAILURE,
                reason_code="PII_MASKING_FAILURE",
                masking_status=MaskingStatus.FAILED,
            )
        try:
            distribution = self._classifier.predict_distribution(masked.text)
        except RuntimeError:
            return self._audit_result(
                action=TriageAction.HUMAN_REVIEW_SYSTEM_FAILURE,
                reason_code="MODEL_UNAVAILABLE",
                masking_status=masked.status,
                input_fingerprint=masked.input_fingerprint,
                masked_entity_counts=masked.entity_counts,
            )
        product, confidence = max(distribution.items(), key=lambda item: item[1])
        eligible = self._probabilities_calibrated and self._policy.allows_auto_route(
            confidence=confidence,
            class_calibration_support=self._class_calibration_support.get(product, 0),
            dependencies_healthy=True,
        )
        return self._audit_result(
            action=(
                TriageAction.AUTO_ROUTE if eligible else TriageAction.HUMAN_REVIEW_LOW_CONFIDENCE
            ),
            reason_code="POLICY_ELIGIBLE" if eligible else "CALIBRATION_OR_POLICY_GATE",
            masking_status=masked.status,
            input_fingerprint=masked.input_fingerprint,
            masked_entity_counts=masked.entity_counts,
            predicted_product=product,
            confidence=confidence,
        )

    def _audit_result(
        self,
        *,
        action: TriageAction,
        reason_code: str,
        masking_status: MaskingStatus,
        input_fingerprint: str | None = None,
        masked_entity_counts: dict[str, int] | None = None,
        predicted_product: str | None = None,
        confidence: float | None = None,
    ) -> TriageResult:
        event = self._audit_store.append(
            AuditEventInput(
                action=action,
                reason_code=reason_code,
                masking_status=masking_status,
                masked_entity_counts=masked_entity_counts or {},
                input_fingerprint=input_fingerprint,
                predicted_product=predicted_product,
                confidence=confidence,
            )
        )
        return TriageResult(
            audit_id=event.audit_id,
            action=action,
            predicted_product=predicted_product,
            confidence=confidence,
            guardrail_status=masking_status,
            reason_code=reason_code,
        )
