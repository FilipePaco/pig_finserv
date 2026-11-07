"""Read-only DuckDB queries for deterministic complaint-report metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import duckdb


@dataclass(frozen=True, slots=True)
class ReportMetrics:
    product: str
    as_of_date: date
    current_count: int
    previous_count: int
    timely_yes_count: int
    timely_known_count: int
    response_distribution: tuple[tuple[str, int], ...]
    top_issues: tuple[tuple[str, int], ...]
    top_companies: tuple[tuple[str, int], ...]
    daily_counts: tuple[tuple[date, int], ...]

    @property
    def volume_change(self) -> float | None:
        if self.previous_count == 0:
            return None
        return (self.current_count - self.previous_count) / self.previous_count

    @property
    def timely_response_rate(self) -> float | None:
        if self.timely_known_count == 0:
            return None
        return self.timely_yes_count / self.timely_known_count


class AnalyticsStore:
    """Expose fixed, parameterized queries over one curated Parquet snapshot."""

    def __init__(self, parquet_path: Path) -> None:
        self._parquet_path = parquet_path

    def report_metrics(self, *, product: str, as_of_date: date) -> ReportMetrics:
        """Return the deterministic metrics required for a product report."""

        current_start = as_of_date - timedelta(days=29)
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=29)
        with self._connection() as connection:
            current_count = self._count(connection, product, current_start, as_of_date)
            previous_count = self._count(connection, product, previous_start, previous_end)
            timely = connection.execute(
                """
                SELECT
                    count(*) FILTER (WHERE timely_response = 'YES'),
                    count(*) FILTER (WHERE timely_response IN ('YES', 'NO'))
                FROM complaints
                WHERE product_canonical = ? AND date_received BETWEEN ? AND ?
                """,
                [product, current_start, as_of_date],
            ).fetchone()
            response_distribution = self._ranked(
                connection,
                "company_response",
                product,
                current_start,
                as_of_date,
                include_null=False,
            )
            top_issues = self._ranked(
                connection, "issue_source", product, current_start, as_of_date, include_null=False
            )[:5]
            top_companies = self._ranked(
                connection,
                "company_canonical",
                product,
                current_start,
                as_of_date,
                include_null=False,
            )[:5]
            dates = tuple(current_start + timedelta(days=index) for index in range(30))
            daily_result = connection.execute(
                """
                SELECT date_received, count(*)
                FROM complaints
                WHERE product_canonical = ? AND date_received BETWEEN ? AND ?
                GROUP BY date_received
                """,
                [product, current_start, as_of_date],
            ).fetchall()
        daily_lookup = {received: count for received, count in daily_result}
        return ReportMetrics(
            product=product,
            as_of_date=as_of_date,
            current_count=current_count,
            previous_count=previous_count,
            timely_yes_count=int(timely[0]),
            timely_known_count=int(timely[1]),
            response_distribution=tuple(response_distribution),
            top_issues=tuple(top_issues),
            top_companies=tuple(top_companies),
            daily_counts=tuple((value, int(daily_lookup.get(value, 0))) for value in dates),
        )

    def _connection(self) -> duckdb.DuckDBPyConnection:
        connection = duckdb.connect(":memory:")
        connection.execute(
            "CREATE VIEW complaints AS SELECT * FROM read_parquet('"
            + _sql_path(self._parquet_path)
            + "')"
        )
        return connection

    @staticmethod
    def _count(connection, product: str, start: date, end: date) -> int:
        return int(
            connection.execute(
                "SELECT count(*) FROM complaints "
                "WHERE product_canonical = ? AND date_received BETWEEN ? AND ?",
                [product, start, end],
            ).fetchone()[0]
        )

    @staticmethod
    def _ranked(
        connection, column: str, product: str, start: date, end: date, *, include_null: bool
    ):
        if column not in {"company_response", "issue_source", "company_canonical"}:
            raise ValueError("unsupported analytics column")
        null_clause = "" if include_null else f" AND {column} IS NOT NULL"
        return connection.execute(
            f"""
            SELECT {column}, count(*) AS volume
            FROM complaints
            WHERE product_canonical = ? AND date_received BETWEEN ? AND ? {null_clause}
            GROUP BY {column}
            ORDER BY volume DESC, {column} ASC
            """,
            [product, start, end],
        ).fetchall()


def _sql_path(path: Path) -> str:
    """Escape an explicit trusted local path for DuckDB's non-parameterizable view DDL."""

    return str(path.resolve()).replace("'", "''")
