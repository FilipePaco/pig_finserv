from datetime import date

from pig_finserv.analytics import ReportMetrics
from pig_finserv.reporting import render_markdown


def test_render_markdown_discloses_zero_denominator_and_limitations() -> None:
    report = render_markdown(
        ReportMetrics(
            product="Credit card", as_of_date=date(2026, 10, 31), current_count=2,
            previous_count=0, timely_yes_count=0, timely_known_count=0,
            response_distribution=(("Closed with explanation", 2),),
            top_issues=(("Billing dispute", 2),),
            top_companies=(("Example Bank", 2),),
            daily_counts=((date(2026, 10, 2), 0), (date(2026, 10, 31), 2)),
        )
    )

    assert "Change: N/A" in report
    assert "(N/A)" in report
    assert "not normalized by company customer base" in report
    assert "| 2026-10-02 | 0 |" in report
    assert "| Closed with explanation | 2 |" in report
    assert "| Billing dispute | 2 |" in report
