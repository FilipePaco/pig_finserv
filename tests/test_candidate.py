from datetime import date

import pytest

from pig_finserv.modeling.calibration import CalibratedProductClassifier
from pig_finserv.modeling.candidate import TfidfLinearSvmProductClassifier
from pig_finserv.modeling.split import LabeledNarrative


def _examples(prefix: str) -> tuple[LabeledNarrative, ...]:
    return (
        LabeledNarrative(f"{prefix}-1", date(2024, 1, 1), "card billing fee", "Credit card"),
        LabeledNarrative(f"{prefix}-2", date(2024, 1, 2), "card payment dispute", "Credit card"),
        LabeledNarrative(f"{prefix}-3", date(2024, 1, 3), "mortgage escrow", "Mortgage"),
        LabeledNarrative(f"{prefix}-4", date(2024, 1, 4), "home mortgage closing", "Mortgage"),
    )


def test_svm_candidate_becomes_probabilistic_only_after_calibration() -> None:
    fitted = TfidfLinearSvmProductClassifier().fit(_examples("fit"))
    calibrated = CalibratedProductClassifier().fit(base=fitted, calibration=_examples("cal"))

    distribution = calibrated.predict_distribution("card billing dispute")

    assert set(distribution) == {"Credit card", "Mortgage"}
    assert sum(distribution.values()) == pytest.approx(1.0)
