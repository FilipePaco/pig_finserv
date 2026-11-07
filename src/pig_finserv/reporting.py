"""Structured Markdown report rendering from deterministic analytics output."""

from __future__ import annotations

from pig_finserv.analytics import ReportMetrics


def render_markdown(metrics: ReportMetrics) -> str:
    """Render a source-free deterministic report before optional commentary is added."""

    change = "N/A" if metrics.volume_change is None else f"{metrics.volume_change:.1%}"
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
            *_table("Response", "Complaints", metrics.response_distribution),
            "",
            "## Top issues",
            *_table("Issue", "Complaints", metrics.top_issues),
            "",
            "## Top companies",
            *_table("Company", "Complaints", metrics.top_companies),
            "",
            "## Limitations",
            "- Complaint volume is not normalized by company customer base or market share.",
            "- Complaint counts are observations, not evidence of causality or wrongdoing.",
            "",
            "## Daily complaints",
            "| Date | Complaints |",
            "| --- | ---: |",
            *[f"| {day.isoformat()} | {count} |" for day, count in metrics.daily_counts],
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
