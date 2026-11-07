"""Leakage-resistant chronological partitions for complaint narratives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


class TemporalSplitError(ValueError):
    """Raised when a snapshot cannot satisfy the required chronological protocol."""


@dataclass(frozen=True, slots=True)
class LabeledNarrative:
    """Minimal masked-text example eligible for supervised product training."""

    complaint_id: str
    date_received: date
    masked_text: str
    product_canonical: str


@dataclass(frozen=True, slots=True)
class TemporalPartitions:
    """Fit, calibration, and locked-test partitions split by full calendar month."""

    fit: tuple[LabeledNarrative, ...]
    calibration: tuple[LabeledNarrative, ...]
    test: tuple[LabeledNarrative, ...]
    fit_months: tuple[tuple[int, int], ...]
    calibration_months: tuple[tuple[int, int], ...]
    test_months: tuple[tuple[int, int], ...]


def split_by_month(
    examples: tuple[LabeledNarrative, ...],
    *,
    fit_month_count: int = 24,
    calibration_month_count: int = 6,
    test_month_count: int = 6,
) -> TemporalPartitions:
    """Create a fixed chronological split with no month shared across partitions."""

    if not examples:
        raise TemporalSplitError("at least one labelled narrative is required")
    months = tuple(
        sorted({(item.date_received.year, item.date_received.month) for item in examples})
    )
    required_months = fit_month_count + calibration_month_count + test_month_count
    if len(months) < required_months:
        raise TemporalSplitError(
            f"snapshot has {len(months)} months but requires at least {required_months}"
        )
    selected = months[-required_months:]
    fit_months = selected[:fit_month_count]
    calibration_months = selected[fit_month_count : fit_month_count + calibration_month_count]
    test_months = selected[-test_month_count:]
    return TemporalPartitions(
        fit=_in_months(examples, fit_months),
        calibration=_in_months(examples, calibration_months),
        test=_in_months(examples, test_months),
        fit_months=fit_months,
        calibration_months=calibration_months,
        test_months=test_months,
    )


def _in_months(
    examples: tuple[LabeledNarrative, ...], months: tuple[tuple[int, int], ...]
) -> tuple[LabeledNarrative, ...]:
    allowed = set(months)
    return tuple(
        item for item in examples if (item.date_received.year, item.date_received.month) in allowed
    )
