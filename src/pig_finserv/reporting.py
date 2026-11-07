"""Structured Markdown report rendering from deterministic analytics output."""

from __future__ import annotations

from pig_finserv.analytics import ReportMetrics


def render_markdown(metrics: ReportMetrics) -> str:
    """Render a source-free deterministic report before optional commentary is added."""

    change = "N/A" if metrics.volume_change is None else f"{metrics.volume_change:.1%}"
    response_known_count = sum(count for _, count in metrics.response_distribution)
    timely = (
        "N/A" if metrics.timely_response_rate is None else f"{metrics.timely_response_rate:.1%}"
    )
    return "\n".join(
        [
            f"# {metrics.product} complaint trend report",
            "",
            f"As of date: {metrics.as_of_date.isoformat()}",
            "",
            "## Volume",
            f"- Current 30-day complaints: {metrics.current_count}",
            f"- Previous 30-day complaints: {metrics.previous_count}",
            f"- Change: {change}",
            "",
            "## Timely response",
            (
                f"- Timely responses: {metrics.timely_yes_count} / "
                f"{metrics.timely_known_count} ({timely})"
            ),
            "",
            "## Company responses",
            *_table_with_share("Response", metrics.response_distribution, response_known_count),
            f"- Excluded/unknown response records: {metrics.current_count - response_known_count}",
            "",
            "## Top issues",
            *_table_with_share("Issue", metrics.top_issues, metrics.current_count),
            "",
            "## Top companies",
            *_table_with_share("Company", metrics.top_companies, metrics.current_count),
            "",
            "## Limitations",
            "- Complaint volume is not normalized by company customer base or market share.",
            "- Complaint counts are observations, not evidence of causality or wrongdoing.",
            "",
            "## Daily complaints",
            "| Date | Complaints |",
            "| --- | ---: |",
            *[f"| {day.isoformat()} | {count} |" for day, count in metrics.daily_counts],
            "",
            "## Monthly complaints",
            "| Month | Complaints |",
            "| --- | ---: |",
            *[f"| {month.isoformat()} | {count} |" for month, count in metrics.monthly_counts],
        ]
    ) + "\n"


def _table(first_column: str, second_column: str, rows: tuple[tuple[str, int], ...]) -> list[str]:
    if not rows:
        return ["No known records in this period."]
    return [
        f"| {first_column} | {second_column} |",
        "| --- | ---: |",
        *[f"| {label} | {count} |" for label, count in rows],
    ]


def _table_with_share(
    first_column: str, rows: tuple[tuple[str, int], ...], denominator: int
) -> list[str]:
    if not rows:
        return ["No known records in this period."]
    return [
        f"| {first_column} | Complaints | Share |",
        "| --- | ---: | ---: |",
        *[
            f"| {label} | {count} | {_share(count, denominator)} |"
            for label, count in rows
        ],
    ]


def _share(count: int, denominator: int) -> str:
    return "N/A" if denominator == 0 else f"{count / denominator:.1%}"
