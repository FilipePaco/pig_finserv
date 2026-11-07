"""Cost-aware, selective routing policy for calibrated classifier probabilities."""

from __future__ import annotations

from dataclasses import dataclass


class ThresholdSelectionError(ValueError):
    """Raised when validation data cannot support a safe auto-route threshold."""


@dataclass(frozen=True, slots=True)
class CalibrationOutcome:
    predicted_product: str
    confidence: float
    is_correct: bool


@dataclass(frozen=True, slots=True)
class ThresholdPolicy:
    threshold: float
    review_cost: float
    misroute_cost: float
    minimum_selective_precision: float
    minimum_class_support: int
    validation_auto_route_coverage: float
    validation_selective_precision: float
    validation_expected_cost: float

    def allows_auto_route(
        self, *, confidence: float, class_calibration_support: int, dependencies_healthy: bool
    ) -> bool:
        return (
            dependencies_healthy
            and confidence >= self.threshold
            and class_calibration_support >= self.minimum_class_support
        )


def select_threshold(
    outcomes: tuple[CalibrationOutcome, ...],
    *,
    review_cost: float = 1.0,
    misroute_cost: float = 10.0,
    minimum_selective_precision: float = 0.90,
    minimum_class_support: int = 50,
) -> ThresholdPolicy:
    """Choose the lowest-cost threshold that meets the selective-precision floor."""

    if not outcomes:
        raise ThresholdSelectionError("at least one calibration outcome is required")
    if review_cost <= 0 or misroute_cost <= 0:
        raise ThresholdSelectionError("costs must be positive")
    if not 0 < minimum_selective_precision <= 1:
        raise ThresholdSelectionError("minimum_selective_precision must be in (0, 1]")
    if minimum_class_support < 1:
        raise ThresholdSelectionError("minimum_class_support must be positive")

    candidates = sorted({outcome.confidence for outcome in outcomes})
    eligible: list[ThresholdPolicy] = []
    for threshold in candidates:
        auto_routed = tuple(outcome for outcome in outcomes if outcome.confidence >= threshold)
        correct = sum(outcome.is_correct for outcome in auto_routed)
        precision = correct / len(auto_routed)
        if precision < minimum_selective_precision:
            continue
        incorrect = len(auto_routed) - correct
        reviews = len(outcomes) - len(auto_routed)
        eligible.append(
            ThresholdPolicy(
                threshold, review_cost, misroute_cost, minimum_selective_precision,
                minimum_class_support, len(auto_routed) / len(outcomes), precision,
                incorrect * misroute_cost + reviews * review_cost,
            )
        )
    if not eligible:
        raise ThresholdSelectionError("no threshold satisfies the selective-precision floor")
    return min(eligible, key=lambda policy: (policy.validation_expected_cost, policy.threshold))
