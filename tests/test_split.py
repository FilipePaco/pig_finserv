from datetime import date

import pytest

from pig_finserv.modeling.split import LabeledNarrative, TemporalSplitError, split_by_month


def _examples(month_count: int) -> tuple[LabeledNarrative, ...]:
    return tuple(
        LabeledNarrative(
            complaint_id=str(index),
            date_received=date(2023 + (index // 12), (index % 12) + 1, 15),
            masked_text=f"[PERSON_1] complaint {index}",
            product_canonical="Credit card",
        )
        for index in range(month_count)
    )


def test_split_by_month_uses_disjoint_full_month_partitions() -> None:
    partitions = split_by_month(_examples(36))

    assert len(partitions.fit_months) == 24
    assert len(partitions.calibration_months) == 6
    assert len(partitions.test_months) == 6
    assert {item.complaint_id for item in partitions.fit}.isdisjoint(
        item.complaint_id for item in partitions.calibration
    )
    assert {item.complaint_id for item in partitions.calibration}.isdisjoint(
        item.complaint_id for item in partitions.test
    )
    assert partitions.test_months[-1] == (2025, 12)


def test_split_by_month_rejects_insufficient_history() -> None:
    with pytest.raises(TemporalSplitError, match="requires at least 36"):
        split_by_month(_examples(35))
