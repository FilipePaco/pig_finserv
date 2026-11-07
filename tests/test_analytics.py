from datetime import date, timedelta
from pathlib import Path

from pig_finserv.analytics import AnalyticsStore
from pig_finserv.data.curated import CuratedComplaint, write_curated_parquet


def _record(index: int, received: date, **overrides) -> CuratedComplaint:
    values = {
        "complaint_id": str(index),
        "date_received": received,
        "product_source": "Credit card",
        "product_canonical": "Credit card",
        "product_mapping_status": "MAPPED",
        "issue_source": "Billing dispute",
        "company_source": "Example Bank",
        "company_canonical": "Example Bank",
        "company_alias_status": "REVIEWED",
        "company_response": "Closed with explanation",
        "timely_response": "YES",
        "snapshot_id": "snapshot-001",
        "source_row_fingerprint": f"{index:064d}",
    }
    values.update(overrides)
    return CuratedComplaint(**values)


def test_report_metrics_uses_fixed_periods_denominators_and_zero_fill(tmp_path: Path) -> None:
    as_of_date = date(2026, 10, 31)
    records = (
        _record(1, as_of_date),
        _record(2, as_of_date - timedelta(days=2), timely_response="NO"),
        _record(3, as_of_date - timedelta(days=5), company_response=None),
        _record(4, as_of_date - timedelta(days=32), issue_source="Fees"),
        _record(5, as_of_date - timedelta(days=40), issue_source="Fees"),
    )
    parquet = tmp_path / "curated.parquet"
    write_curated_parquet(records, parquet)

    metrics = AnalyticsStore(parquet).report_metrics(product="Credit card", as_of_date=as_of_date)

    assert metrics.current_count == 3
    assert metrics.previous_count == 2
    assert metrics.volume_change == 0.5
    assert metrics.timely_yes_count == 2
    assert metrics.timely_known_count == 3
    assert metrics.timely_response_rate == 2 / 3
    assert metrics.response_distribution == (("Closed with explanation", 2),)
    assert metrics.top_issues == (("Billing dispute", 3),)
    assert metrics.top_companies == (("Example Bank", 3),)
    assert len(metrics.daily_counts) == 30
    assert metrics.daily_counts[0] == (as_of_date - timedelta(days=29), 0)
    assert metrics.daily_counts[-1] == (as_of_date, 1)
