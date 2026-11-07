from datetime import date
from pathlib import Path

from pig_finserv.analytics import ReportMetrics
from pig_finserv.charts import render_report_charts


def test_render_report_charts_writes_daily_and_monthly_assets(tmp_path: Path) -> None:
    metrics = ReportMetrics(
        product="Credit card",
        as_of_date=date(2026, 10, 31),
        current_count=1,
        previous_count=1,
        timely_yes_count=1,
        timely_known_count=1,
        response_distribution=(),
        top_issues=(),
        top_companies=(),
        daily_counts=((date(2026, 10, 30), 0), (date(2026, 10, 31), 1)),
        monthly_counts=((date(2026, 9, 1), 0), (date(2026, 10, 1), 1)),
    )

    daily, monthly = render_report_charts(metrics, tmp_path)

    assert daily.exists() and daily.stat().st_size > 0
    assert monthly.exists() and monthly.stat().st_size > 0
