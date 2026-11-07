"""Probability calibration for a frozen local product classifier."""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator

from pig_finserv.modeling.baseline import TfidfLogisticProductClassifier
from pig_finserv.modeling.split import LabeledNarrative


@dataclass
class CalibratedProductClassifier:
    """Sigmoid-calibrated probabilities fitted only on the later validation partition."""

    estimator: CalibratedClassifierCV | None = None

    def fit(
        self, *, base: TfidfLogisticProductClassifier, calibration: tuple[LabeledNarrative, ...]
    ) -> CalibratedProductClassifier:
        if base.pipeline is None:
            raise ValueError("base classifier must be fitted before calibration")
        if len({item.product_canonical for item in calibration}) < 2:
            raise ValueError("calibration data must contain at least two product classes")
        self.estimator = CalibratedClassifierCV(
            estimator=FrozenEstimator(base.pipeline), method="sigmoid", cv=2
        ).fit(
            [item.masked_text for item in calibration],
            [item.product_canonical for item in calibration],
        )
        return self

    def predict_distribution(self, masked_text: str) -> dict[str, float]:
        if self.estimator is None:
            raise RuntimeError("classifier must be calibrated before prediction")
        probabilities = self.estimator.predict_proba([masked_text])[0]
        return {
            label: float(probability)
            for label, probability in zip(self.estimator.classes_, probabilities, strict=True)
        }
