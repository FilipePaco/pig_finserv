from datetime import UTC, datetime
from pathlib import Path

from pig_finserv.data.ingestion import ingest_csv
from pig_finserv.data.mapping import CompanyAliasMapper, TaxonomyMapper


def test_ingest_csv_writes_safe_parquet_and_manifest(tmp_path: Path) -> None:
    source = tmp_path / "complaints.csv"
    source.write_text(
        "Complaint ID,Date received,Product,Company,Consumer complaint narrative\n"
        "100,2026-10-31,Credit card,Example Bank,Call me at 555-0100\n"
    )
    result = ingest_csv(
        source_path=source,
        output_directory=tmp_path / "output",
        taxonomy_mapper=TaxonomyMapper(tuple()),
        company_mapper=CompanyAliasMapper(tuple()),
        taxonomy_version="2026.1",
        company_alias_version="2026.1",
        retrieved_at=datetime(2026, 11, 1, tzinfo=UTC),
    )

    assert result.parquet_path.exists()
    assert result.manifest_path.exists()
    assert result.manifest.accepted_row_count == 1
    assert result.mapping_quality == {"MAPPED": 0, "UNMAPPED": 1, "AMBIGUOUS": 0}
    assert "555-0100" not in result.manifest_path.read_text()
