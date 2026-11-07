import pytest

from pig_finserv.modeling.policy import (
    CalibrationOutcome,
    ThresholdSelectionError,
    select_threshold,
)


def test_select_threshold_minimizes_cost_subject_to_precision_floor() -> None:
    outcomes = (
        CalibrationOutcome("Credit card", 0.99, True),
        CalibrationOutcome("Credit card", 0.95, True),
        CalibrationOutcome("Mortgage", 0.90, True),
        CalibrationOutcome("Mortgage", 0.85, False),
        CalibrationOutcome("Mortgage", 0.70, False),
    )

    policy = select_threshold(
        outcomes,
        review_cost=1,
        misroute_cost=10,
        minimum_selective_precision=0.90,
        minimum_class_support=2,
    )

    assert policy.threshold == 0.90
    assert policy.validation_auto_route_coverage == pytest.approx(0.60)
    assert policy.validation_selective_precision == 1.0
    assert policy.allows_auto_route(
        confidence=0.90, class_calibration_support=2, dependencies_healthy=True
    )
    assert not policy.allows_auto_route(
        confidence=0.89, class_calibration_support=2, dependencies_healthy=True
    )
    assert not policy.allows_auto_route(
        confidence=0.99, class_calibration_support=1, dependencies_healthy=True
    )


def test_select_threshold_rejects_unsafe_calibration_results() -> None:
    outcomes = (CalibrationOutcome("Credit card", 0.80, False),)

    with pytest.raises(ThresholdSelectionError, match="no threshold"):
        select_threshold(outcomes, minimum_selective_precision=0.90)
