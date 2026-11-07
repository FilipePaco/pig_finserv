from datetime import date
from pathlib import Path

import duckdb

from pig_finserv.data.curated import curate_records, mapping_quality, write_curated_parquet
from pig_finserv.data.mapping import (
    CompanyAliasEntry,
    CompanyAliasMapper,
    ProductMappingEntry,
    TaxonomyMapper,
)
from pig_finserv.data.schema import resolve_schema, validate_rows


def _validated_records():
    schema = resolve_schema(
        [
            "Complaint ID",
            "Date received",
            "Product",
            "Company",
            "Consumer complaint narrative",
        ]
    )
    return validate_rows(
        [
            {
                "Complaint ID": "100",
                "Date received": "2026-10-31",
                "Product": "Credit card",
                "Company": "Example Bank N.A.",
                "Consumer complaint narrative": "Call me at 555-0100",
            },
            {
                "Complaint ID": "101",
                "Date received": "2026-10-31",
                "Product": "Unmapped product",
                "Company": "Unknown Company",
                "Consumer complaint narrative": "My name is Taylor",
            },
        ],
        schema=schema,
        snapshot_id="snapshot-001",
    ).records


def test_curated_records_apply_reviewed_mappings_without_narratives() -> None:
    curated = curate_records(
        _validated_records(),
        taxonomy_mapper=TaxonomyMapper(
            (
                ProductMappingEntry(
                    date(2020, 1, 1),
                    None,
                    "Credit card",
                    None,
                    "Credit card",
                    "Current taxonomy label",
                    "2026.1",
                ),
            )
        ),
        company_mapper=CompanyAliasMapper(
            (
                CompanyAliasEntry(
                    "Example Bank N.A.",
                    "Example Bank",
                    "Reviewed alias",
                    "data-owner",
                    "2026.1",
                ),
            )
        ),
    )

    assert curated[0].product_canonical == "Credit card"
    assert curated[0].company_canonical == "Example Bank"
    assert curated[1].product_mapping_status == "UNMAPPED"
    assert mapping_quality(curated) == {"MAPPED": 1, "UNMAPPED": 1, "AMBIGUOUS": 0}
    assert not hasattr(curated[0], "narrative_restricted")


def test_write_curated_parquet_excludes_restricted_narrative(tmp_path: Path) -> None:
    curated = curate_records(
        _validated_records(),
        taxonomy_mapper=TaxonomyMapper(tuple()),
        company_mapper=CompanyAliasMapper(tuple()),
    )
    output = tmp_path / "curated.parquet"

    checksum = write_curated_parquet(curated, output)

    connection = duckdb.connect(":memory:")
    try:
        columns = {
            row[0]
            for row in connection.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)", [str(output)]
            ).fetchall()
        }
        contents = connection.execute("SELECT * FROM read_parquet(?)", [str(output)]).fetchall()
    finally:
        connection.close()

    assert output.exists()
    assert len(checksum) == 64
    assert "narrative_restricted" not in columns
    assert "555-0100" not in str(contents)
