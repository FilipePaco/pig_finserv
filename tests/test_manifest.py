from datetime import UTC, datetime
from pathlib import Path

import pytest

from pig_finserv.data.manifest import (
    build_snapshot_manifest,
    sha256_file,
    write_manifest,
)
from pig_finserv.data.schema import resolve_schema, validate_rows


@pytest.fixture
def validation_fixture():
    schema = resolve_schema(["Complaint ID", "Date received", "Product"])
    validation = validate_rows(
        [
            {
                "Complaint ID": "100",
                "Date received": "2026-10-30",
                "Product": "Credit card",
            },
            {
                "Complaint ID": "101",
                "Date received": "2026-10-31",
                "Product": "Mortgage",
            },
        ],
        schema=schema,
        snapshot_id="not-used-by-manifest",
    )
    return schema, validation


def test_build_manifest_is_complete_and_excludes_restricted_narratives(validation_fixture) -> None:
    schema, validation = validation_fixture
    manifest = build_snapshot_manifest(
        acquisition_method="fixture",
        source_reference="fixture.csv",
        retrieved_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        source_checksum="a" * 64,
        source_row_count=2,
        schema=schema,
        validation=validation,
        taxonomy_version="2026.1",
        company_alias_version="2026.1",
        software_version="0.1.0",
    )

    assert manifest.snapshot_id == "cfpb-55088c6003332d74"
    assert manifest.accepted_row_count == 2
    assert manifest.date_min == "2026-10-30"
    assert manifest.date_max == "2026-10-31"
    assert "narrative_restricted" not in manifest.as_dict()["source_schema_mapping"]


def test_manifest_requires_timezone_aware_retrieval_time(validation_fixture) -> None:
    schema, validation = validation_fixture

    with pytest.raises(ValueError, match="timezone-aware"):
        build_snapshot_manifest(
            acquisition_method="fixture",
            source_reference="fixture.csv",
            retrieved_at=datetime(2026, 11, 1, 12, 0),
            source_checksum="a" * 64,
            source_row_count=2,
            schema=schema,
            validation=validation,
            taxonomy_version="2026.1",
            company_alias_version="2026.1",
            software_version="0.1.0",
        )


def test_write_manifest_and_checksum_are_deterministic(tmp_path: Path, validation_fixture) -> None:
    schema, validation = validation_fixture
    manifest = build_snapshot_manifest(
        acquisition_method="fixture",
        source_reference="fixture.csv",
        retrieved_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        source_checksum="a" * 64,
        source_row_count=2,
        schema=schema,
        validation=validation,
        taxonomy_version="2026.1",
        company_alias_version="2026.1",
        software_version="0.1.0",
    )
    destination = tmp_path / "manifests" / "snapshot.json"

    write_manifest(manifest, destination)

    assert destination.exists()
    assert sha256_file(destination) == sha256_file(destination)
    assert "fixture.csv" in destination.read_text()
