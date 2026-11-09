"""Read-only DuckDB queries for deterministic complaint-report metrics."""

from __future__ import annotations

import hashlib
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
    monthly_counts: tuple[tuple[date, int], ...]
    snapshot_id: str = "unknown"

    @property
    def report_id(self) -> str:
        """Return a stable identifier derived only from report lineage and filters."""

        material = f"{self.snapshot_id}:{self.product}:{self.as_of_date.isoformat()}"
        return f"report-{hashlib.sha256(material.encode()).hexdigest()[:16]}"

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
            snapshot_ids = connection.execute(
                "SELECT DISTINCT snapshot_id FROM complaints"
            ).fetchall()
            if len(snapshot_ids) != 1:
                raise ValueError("curated Parquet must contain exactly one snapshot_id")
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
            monthly_result = connection.execute(
                """
                SELECT date_trunc('month', date_received)::DATE, count(*)
                FROM complaints
                WHERE product_canonical = ? AND date_received BETWEEN ? AND ?
                GROUP BY date_trunc('month', date_received)::DATE
                """,
                [product, _shift_months(_month_start(as_of_date), -11), as_of_date],
            ).fetchall()
        daily_lookup = {received: count for received, count in daily_result}
        monthly_lookup = {received: count for received, count in monthly_result}
        months = tuple(_shift_months(_month_start(as_of_date), offset) for offset in range(-11, 1))
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
            monthly_counts=tuple((value, int(monthly_lookup.get(value, 0))) for value in months),
            snapshot_id=str(snapshot_ids[0][0]),
        )

    def coverage_dates(self) -> tuple[date, date]:
        """Return the snapshot boundaries needed to validate an as-of date."""

        with self._connection() as connection:
            earliest, latest = connection.execute(
                "SELECT min(date_received), max(date_received) FROM complaints"
            ).fetchone()
        if earliest is None or latest is None:
            raise ValueError("curated snapshot has no complaint dates")
        return earliest, latest

    def canonical_products(self) -> tuple[str, ...]:
        """Return the fixed, non-empty canonical products available for reporting."""

        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT product_canonical
                FROM complaints
                WHERE product_canonical IS NOT NULL AND product_canonical <> ''
                ORDER BY product_canonical
                """
            ).fetchall()
        products = tuple(str(row[0]) for row in rows)
        if not products:
            raise ValueError("curated snapshot has no canonical products")
        return products

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


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _shift_months(value: date, delta: int) -> date:
    ordinal = value.year * 12 + value.month - 1 + delta
    return date(ordinal // 12, ordinal % 12 + 1, 1)
