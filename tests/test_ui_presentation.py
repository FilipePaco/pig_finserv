from pig_finserv.domain import MaskingStatus, TriageAction
from pig_finserv.triage import TriageResult, TriageWorkflowState
from pig_finserv.ui.presentation import triage_view


def test_triage_view_exposes_only_operator_safe_result_fields() -> None:
    view = triage_view(
        TriageResult(
            audit_id="triage_123",
            action=TriageAction.HUMAN_REVIEW_LOW_CONFIDENCE,
            predicted_product="Credit card",
            confidence=0.7123,
            guardrail_status=MaskingStatus.MASKED,
            reason_code="CALIBRATION_OR_POLICY_GATE",
            workflow_state=TriageWorkflowState.AUDITED,
        )
    )

    assert view.confidence_percent == "71.2%"
    assert view.requires_human_review is True
    assert "narrative" not in view.__dataclass_fields__
