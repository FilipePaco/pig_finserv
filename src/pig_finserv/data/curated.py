"""Curated, non-narrative analytics snapshots stored as Parquet."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb

from pig_finserv.data.mapping import CompanyAliasMapper, TaxonomyMapper
from pig_finserv.data.schema import ComplaintRecord
from pig_finserv.domain import MappingStatus


@dataclass(frozen=True, slots=True)
class CuratedComplaint:
    """Analytics-safe complaint record with source lineage and reviewed mappings."""

    complaint_id: str
    date_received: date
    product_source: str
    product_canonical: str | None
    product_mapping_status: str
    issue_source: str | None
    company_source: str | None
    company_canonical: str | None
    company_alias_status: str
    company_response: str | None
    timely_response: str
    snapshot_id: str
    source_row_fingerprint: str


def curate_records(
    records: tuple[ComplaintRecord, ...],
    *,
    taxonomy_mapper: TaxonomyMapper,
    company_mapper: CompanyAliasMapper,
) -> tuple[CuratedComplaint, ...]:
    """Apply only reviewed mappings and omit restricted narrative text from analytics."""

    curated: list[CuratedComplaint] = []
    for record in records:
        product = taxonomy_mapper.map_product(
            source_product=record.product_source,
            source_sub_product=record.sub_product_source,
            received=record.date_received,
        )
        company = company_mapper.map_company(record.company_source)
        curated.append(
            CuratedComplaint(
                complaint_id=record.complaint_id,
                date_received=record.date_received,
                product_source=record.product_source,
                product_canonical=product.canonical_product,
                product_mapping_status=product.status.value,
                issue_source=record.issue_source,
                company_source=record.company_source,
                company_canonical=company.company_canonical,
                company_alias_status=company.status,
                company_response=record.company_response,
                timely_response=record.timely_response,
                snapshot_id=record.snapshot_id,
                source_row_fingerprint=record.source_row_fingerprint,
            )
        )
    return tuple(curated)


def write_curated_parquet(records: tuple[CuratedComplaint, ...], destination: Path) -> str:
    """Write an explicit analytics-safe Parquet file and return its SHA-256 checksum."""

    if not records:
        raise ValueError("cannot write an empty curated snapshot")
    destination.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(":memory:")
    try:
        connection.execute(
            """
            CREATE TABLE complaints (
                complaint_id VARCHAR,
                date_received DATE,
                product_source VARCHAR,
                product_canonical VARCHAR,
                product_mapping_status VARCHAR,
                issue_source VARCHAR,
                company_source VARCHAR,
                company_canonical VARCHAR,
                company_alias_status VARCHAR,
                company_response VARCHAR,
                timely_response VARCHAR,
                snapshot_id VARCHAR,
                source_row_fingerprint VARCHAR
            )
            """
        )
        connection.executemany(
            "INSERT INTO complaints VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    record.complaint_id,
                    record.date_received,
                    record.product_source,
                    record.product_canonical,
                    record.product_mapping_status,
                    record.issue_source,
                    record.company_source,
                    record.company_canonical,
                    record.company_alias_status,
                    record.company_response,
                    record.timely_response,
                    record.snapshot_id,
                    record.source_row_fingerprint,
                )
                for record in records
            ],
        )
        connection.execute(f"COPY complaints TO '{_sql_path(destination)}' (FORMAT PARQUET)")
    finally:
        connection.close()
    return _sha256_file(destination)


def mapping_quality(records: tuple[CuratedComplaint, ...]) -> dict[str, int]:
    """Return explicit product-mapping quality counts for a curated snapshot."""

    counts = {status.value: 0 for status in MappingStatus}
    for record in records:
        counts[record.product_mapping_status] += 1
    return counts


def _sql_path(path: Path) -> str:
    """Escape an explicit trusted local path for DuckDB COPY syntax."""

    return str(path.resolve()).replace("'", "''")


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
