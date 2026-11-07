from datetime import date

import pytest

from pig_finserv.modeling.baseline import TfidfLogisticProductClassifier
from pig_finserv.modeling.split import LabeledNarrative


def _examples() -> tuple[LabeledNarrative, ...]:
    return (
        LabeledNarrative("1", date(2024, 1, 1), "card billing fee", "Credit card"),
        LabeledNarrative("2", date(2024, 1, 2), "credit card payment", "Credit card"),
        LabeledNarrative("3", date(2024, 1, 3), "mortgage escrow payment", "Mortgage"),
        LabeledNarrative("4", date(2024, 1, 4), "home mortgage closing", "Mortgage"),
    )


def test_baseline_returns_full_probability_distribution() -> None:
    classifier = TfidfLogisticProductClassifier().fit(_examples())

    distribution = classifier.predict_distribution("credit card billing dispute")

    assert set(distribution) == {"Credit card", "Mortgage"}
    assert sum(distribution.values()) == pytest.approx(1.0)
    assert distribution["Credit card"] > distribution["Mortgage"]


def test_baseline_rejects_single_class_training() -> None:
    with pytest.raises(ValueError, match="two product classes"):
        TfidfLogisticProductClassifier().fit(_examples()[:1])
