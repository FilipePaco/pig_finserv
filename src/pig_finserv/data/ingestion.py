"""End-to-end CSV ingestion into a curated Parquet snapshot and manifest."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pig_finserv import __version__
from pig_finserv.data.curated import curate_records, mapping_quality, write_curated_parquet
from pig_finserv.data.manifest import (
    SnapshotManifest,
    build_snapshot_manifest,
    sha256_file,
    snapshot_id_for,
    write_manifest,
)
from pig_finserv.data.mapping import CompanyAliasMapper, TaxonomyMapper
from pig_finserv.data.schema import resolve_schema, validate_rows


@dataclass(frozen=True, slots=True)
class IngestionResult:
    snapshot_id: str
    parquet_path: Path
    manifest_path: Path
    manifest: SnapshotManifest
    mapping_quality: dict[str, int]


def ingest_csv(
    *,
    source_path: Path,
    output_directory: Path,
    taxonomy_mapper: TaxonomyMapper,
    company_mapper: CompanyAliasMapper,
    taxonomy_version: str,
    company_alias_version: str,
    retrieved_at: datetime | None = None,
) -> IngestionResult:
    """Validate one local CFPB CSV and persist analytics-safe outputs only."""

    acquired_at = retrieved_at or datetime.now(UTC)
    if acquired_at.tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware")
    checksum = sha256_file(source_path)
    snapshot_id = snapshot_id_for(source_checksum=checksum, retrieved_at=acquired_at)
    with source_path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        schema = resolve_schema(reader.fieldnames or [])
        rows = tuple(reader)
    validation = validate_rows(rows, schema=schema, snapshot_id=snapshot_id)
    curated = curate_records(
        validation.records, taxonomy_mapper=taxonomy_mapper, company_mapper=company_mapper
    )
    if not curated:
        raise ValueError("ingestion produced no valid curated records")
    output_directory.mkdir(parents=True, exist_ok=True)
    parquet_path = output_directory / f"{snapshot_id}.parquet"
    output_checksum = write_curated_parquet(curated, parquet_path)
    manifest = build_snapshot_manifest(
        acquisition_method="local_csv",
        source_reference=source_path.name,
        retrieved_at=acquired_at,
        source_checksum=checksum,
        source_row_count=len(rows),
        schema=schema,
        validation=validation,
        taxonomy_version=taxonomy_version,
        company_alias_version=company_alias_version,
        output_checksum=output_checksum,
        software_version=__version__,
    )
    manifest_path = output_directory / f"{snapshot_id}.manifest.json"
    write_manifest(manifest, manifest_path)
    return IngestionResult(
        snapshot_id=snapshot_id,
        parquet_path=parquet_path,
        manifest_path=manifest_path,
        manifest=manifest,
        mapping_quality=mapping_quality(curated),
    )
