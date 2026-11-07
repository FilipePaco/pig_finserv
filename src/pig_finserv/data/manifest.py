"""Versioned snapshot manifests for reproducible CFPB ingestion lineage."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from pig_finserv.data.schema import SourceSchema, ValidationResult


@dataclass(frozen=True, slots=True)
class SnapshotManifest:
    """Non-sensitive lineage for one curated complaint-data snapshot."""

    snapshot_id: str
    acquisition_method: str
    source_reference: str
    retrieved_at: str
    source_checksum: str
    source_schema_mapping: dict[str, str]
    source_row_count: int
    accepted_row_count: int
    duplicate_row_count: int
    rejected_row_count: int
    rejection_counts: dict[str, int]
    taxonomy_version: str
    company_alias_version: str
    date_min: str | None
    date_max: str | None
    output_checksum: str | None
    software_version: str

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation with deterministic mapping order."""

        payload = asdict(self)
        payload["source_schema_mapping"] = dict(sorted(self.source_schema_mapping.items()))
        payload["rejection_counts"] = dict(sorted(self.rejection_counts.items()))
        return payload


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 checksum without loading a source file into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_snapshot_manifest(
    *,
    acquisition_method: str,
    source_reference: str,
    retrieved_at: datetime,
    source_checksum: str,
    source_row_count: int,
    schema: SourceSchema,
    validation: ValidationResult,
    taxonomy_version: str,
    company_alias_version: str,
    software_version: str,
    output_checksum: str | None = None,
) -> SnapshotManifest:
    """Build a manifest from validated rows without including restricted narratives."""

    if retrieved_at.tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware")
    if source_row_count < len(validation.records):
        raise ValueError("source_row_count cannot be smaller than accepted_row_count")

    snapshot_id = _snapshot_id(source_checksum=source_checksum, retrieved_at=retrieved_at)
    received_dates = [record.date_received for record in validation.records]
    return SnapshotManifest(
        snapshot_id=snapshot_id,
        acquisition_method=acquisition_method,
        source_reference=source_reference,
        retrieved_at=retrieved_at.astimezone(UTC).isoformat(),
        source_checksum=source_checksum,
        source_schema_mapping=schema.columns,
        source_row_count=source_row_count,
        accepted_row_count=len(validation.records),
        duplicate_row_count=validation.duplicates,
        rejected_row_count=len(validation.rejected_rows),
        rejection_counts=validation.rejection_counts,
        taxonomy_version=taxonomy_version,
        company_alias_version=company_alias_version,
        date_min=min(received_dates).isoformat() if received_dates else None,
        date_max=max(received_dates).isoformat() if received_dates else None,
        output_checksum=output_checksum,
        software_version=software_version,
    )


def write_manifest(manifest: SnapshotManifest, path: Path) -> None:
    """Write a canonical, non-sensitive JSON manifest to an explicit destination."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.as_dict(), indent=2, sort_keys=True) + "\n")


def _snapshot_id(*, source_checksum: str, retrieved_at: datetime) -> str:
    material = f"{source_checksum}:{retrieved_at.astimezone(UTC).isoformat()}"
    return f"cfpb-{hashlib.sha256(material.encode()).hexdigest()[:16]}"
