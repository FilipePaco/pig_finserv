"""Pure, raw-text-free view models for the Streamlit presentation layer."""

from __future__ import annotations

from dataclasses import dataclass

from pig_finserv.triage import TriageResult


@dataclass(frozen=True, slots=True)
class TriageView:
    """Operator-safe triage values permitted in the browser."""

    audit_id: str
    action: str
    predicted_product: str | None
    confidence_percent: str
    guardrail_status: str
    reason_code: str
    requires_human_review: bool


def triage_view(result: TriageResult) -> TriageView:
    """Map a typed result without carrying a complaint narrative into UI state."""

    confidence = (
        f"{result.confidence:.1%}" if result.confidence is not None else "Not available"
    )
    return TriageView(
        audit_id=result.audit_id,
        action=result.action.value,
        predicted_product=result.predicted_product,
        confidence_percent=confidence,
        guardrail_status=result.guardrail_status.value,
        reason_code=result.reason_code,
        requires_human_review=result.action.value != "AUTO_ROUTE",
    )
