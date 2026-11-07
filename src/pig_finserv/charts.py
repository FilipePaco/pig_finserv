"""Accessible static charts rendered from deterministic analytics series."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from pig_finserv.analytics import ReportMetrics


def render_report_charts(metrics: ReportMetrics, output_directory: Path) -> tuple[Path, Path]:
    """Render daily and monthly PNG charts and return their explicit output paths."""

    output_directory.mkdir(parents=True, exist_ok=True)
    daily_path = output_directory / "daily-complaints.png"
    monthly_path = output_directory / "monthly-complaints.png"
    _render_series(
        metrics.daily_counts,
        title=f"Daily {metrics.product} complaints (last 30 days)",
        x_label="Date received",
        output_path=daily_path,
        locator=mdates.DayLocator(interval=5),
        formatter=mdates.DateFormatter("%b %d"),
    )
    _render_series(
        metrics.monthly_counts,
        title=f"Monthly {metrics.product} complaints (last 12 months)",
        x_label="Month received",
        output_path=monthly_path,
        locator=mdates.MonthLocator(interval=2),
        formatter=mdates.DateFormatter("%b\n%Y"),
    )
    return daily_path, monthly_path


def _render_series(
    series, *, title: str, x_label: str, output_path: Path, locator, formatter
) -> None:
    dates, counts = zip(*series, strict=True)
    figure, axis = plt.subplots(figsize=(10, 4.5))
    axis.plot(dates, counts, color="#0b5cab", marker="o", linewidth=2)
    axis.fill_between(dates, counts, color="#0b5cab", alpha=0.12)
    axis.set_title(title)
    axis.set_xlabel(x_label)
    axis.set_ylabel("Complaints")
    axis.xaxis.set_major_locator(locator)
    axis.xaxis.set_major_formatter(formatter)
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_path, dpi=160)
    plt.close(figure)
