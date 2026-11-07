from datetime import date
from pathlib import Path

from pig_finserv.audit import AuditStore
from pig_finserv.domain import TriageAction, TriageRequest
from pig_finserv.modeling.baseline import TfidfLogisticProductClassifier
from pig_finserv.modeling.policy import CalibrationOutcome, select_threshold
from pig_finserv.modeling.split import LabeledNarrative
from pig_finserv.safety.pii import PiiMasker
from pig_finserv.triage import TriageService


def _service(tmp_path: Path, *, calibrated: bool) -> TriageService:
    examples = (
        LabeledNarrative("1", date(2024, 1, 1), "card fee", "Credit card"),
        LabeledNarrative("2", date(2024, 1, 2), "card payment", "Credit card"),
        LabeledNarrative("3", date(2024, 1, 3), "mortgage escrow", "Mortgage"),
        LabeledNarrative("4", date(2024, 1, 4), "home mortgage", "Mortgage"),
    )
    policy = select_threshold(
        (
            CalibrationOutcome("Credit card", 0.50, True),
            CalibrationOutcome("Mortgage", 0.51, True),
        ),
        minimum_selective_precision=0.90,
        minimum_class_support=2,
    )
    return TriageService(
        masker=PiiMasker(fingerprint_salt=b"test-salt"),
        classifier=TfidfLogisticProductClassifier().fit(examples),
        policy=policy,
        class_calibration_support={"Credit card": 2, "Mortgage": 2},
        audit_store=AuditStore(tmp_path / "audit.sqlite"),
        probabilities_calibrated=calibrated,
    )


def test_uncalibrated_model_fails_closed_to_human_review(tmp_path: Path) -> None:
    result = _service(tmp_path, calibrated=False).triage(
        TriageRequest(narrative="My card fee was charged twice. Email a@b.com")
    )

    assert result.action is TriageAction.HUMAN_REVIEW_LOW_CONFIDENCE
    assert result.predicted_product == "Credit card"
    assert result.audit_id.startswith("triage_")


def test_calibrated_eligible_model_can_suggest_auto_route(tmp_path: Path) -> None:
    result = _service(tmp_path, calibrated=True).triage(
        TriageRequest(narrative="My card fee was charged twice.")
    )

    assert result.action is TriageAction.AUTO_ROUTE
    assert result.predicted_product == "Credit card"


def test_empty_narrative_creates_safe_review_event(tmp_path: Path) -> None:
    result = _service(tmp_path, calibrated=True).triage(TriageRequest(narrative=" \n"))

    assert result.action is TriageAction.HUMAN_REVIEW_EMPTY_INPUT
    assert result.predicted_product is None
