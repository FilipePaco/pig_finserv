from datetime import date

import pytest

from pig_finserv.modeling.evaluation import evaluate_classifier
from pig_finserv.modeling.split import LabeledNarrative


class _Classifier:
    def predict_distribution(self, masked_text: str) -> dict[str, float]:
        if "card" in masked_text:
            return {"Credit card": 0.9, "Mortgage": 0.1}
        return {"Credit card": 0.2, "Mortgage": 0.8}


def _examples() -> tuple[LabeledNarrative, ...]:
    return (
        LabeledNarrative("1", date(2025, 1, 1), "card fee", "Credit card"),
        LabeledNarrative("2", date(2025, 1, 2), "mortgage escrow", "Mortgage"),
        LabeledNarrative("3", date(2025, 1, 3), "wrong route", "Credit card"),
    )


def test_evaluation_includes_locked_holdout_quality_calibration_and_costs() -> None:
    result = evaluate_classifier(
        _Classifier(), _examples(), threshold=0.85, reliability_bin_count=2
    )

    assert result.labels == ("Credit card", "Mortgage")
    assert result.accuracy == pytest.approx(2 / 3)
    assert result.confusion_matrix == ((1, 1), (0, 1))
    assert len(result.reliability_bins) == 2
    assert len(result.selective_metrics) == 3
    assert result.selective_metrics[0].auto_route_coverage == 1 / 3
    assert result.selective_metrics[0].expected_cost == 2.0
    assert result.as_dict()["per_class"]["Credit card"]["support"] == 2  # type: ignore[index]


def test_evaluation_validates_threshold_and_examples() -> None:
    with pytest.raises(ValueError, match="holdout"):
        evaluate_classifier(_Classifier(), (), threshold=0.5)
    with pytest.raises(ValueError, match="threshold"):
        evaluate_classifier(_Classifier(), _examples(), threshold=1.1)
