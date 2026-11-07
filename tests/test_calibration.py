from datetime import date

import pytest

from pig_finserv.modeling.baseline import TfidfLogisticProductClassifier
from pig_finserv.modeling.calibration import CalibratedProductClassifier
from pig_finserv.modeling.split import LabeledNarrative


def _examples(prefix: str) -> tuple[LabeledNarrative, ...]:
    return (
        LabeledNarrative(f"{prefix}-1", date(2024, 1, 1), "card billing fee", "Credit card"),
        LabeledNarrative(f"{prefix}-2", date(2024, 1, 2), "card payment dispute", "Credit card"),
        LabeledNarrative(f"{prefix}-3", date(2024, 1, 3), "mortgage escrow", "Mortgage"),
        LabeledNarrative(f"{prefix}-4", date(2024, 1, 4), "home mortgage closing", "Mortgage"),
    )


def test_calibration_wraps_fitted_classifier_without_refitting_it() -> None:
    base = TfidfLogisticProductClassifier().fit(_examples("fit"))
    calibrated = CalibratedProductClassifier().fit(base=base, calibration=_examples("cal"))

    distribution = calibrated.predict_distribution("card billing dispute")

    assert set(distribution) == {"Credit card", "Mortgage"}
    assert sum(distribution.values()) == pytest.approx(1.0)


def test_calibration_requires_fitted_base_and_multiple_classes() -> None:
    with pytest.raises(ValueError, match="base classifier"):
        CalibratedProductClassifier().fit(
            base=TfidfLogisticProductClassifier(), calibration=_examples("cal")
        )
