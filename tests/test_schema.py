from datetime import date

import pytest

from pig_finserv.data.schema import SchemaValidationError, resolve_schema, validate_rows


def test_resolve_schema_supports_cfpb_field_names() -> None:
    schema = resolve_schema(
        [
            "Complaint ID",
            "Date received",
            "Product",
            "Consumer complaint narrative",
            "Timely response?",
        ]
    )

    assert schema.source_column("complaint_id") == "Complaint ID"
    assert schema.source_column("narrative_restricted") == "Consumer complaint narrative"


def test_resolve_schema_rejects_missing_required_columns() -> None:
    with pytest.raises(SchemaValidationError, match="date_received"):
        resolve_schema(["Complaint ID", "Product"])


def test_validate_rows_rejects_bad_rows_deduplicates_and_normalizes_values() -> None:
    schema = resolve_schema(
        [
            "Complaint ID",
            "Date received",
            "Product",
            "Issue",
            "Company",
            "Timely response?",
            "Date sent to company",
        ]
    )
    result = validate_rows(
        [
            {
                "Complaint ID": "100",
                "Date received": "10/31/2026",
                "Product": " Credit card ",
                "Issue": " Billing dispute ",
                "Company": "Example Bank",
                "Timely response?": "Yes",
                "Date sent to company": "2026-11-01",
            },
            {
                "Complaint ID": "100",
                "Date received": "10/31/2026",
                "Product": "Credit card",
                "Issue": "Billing dispute",
                "Company": "Example Bank",
                "Timely response?": "No",
                "Date sent to company": "2026-11-01",
            },
            {"Complaint ID": "101", "Date received": "not-a-date", "Product": "Mortgage"},
            {"Complaint ID": "", "Date received": "2026-10-30", "Product": "Mortgage"},
            {
                "Complaint ID": "102",
                "Date received": "2026-10-30",
                "Product": "Mortgage",
                "Timely response?": "Maybe",
            },
        ],
        schema=schema,
        snapshot_id="snapshot-001",
    )

    assert len(result.records) == 2
    assert result.duplicates == 1
    assert result.rejection_counts == {
        "INVALID_DATE_RECEIVED": 1,
        "MISSING_COMPLAINT_ID": 1,
    }
    first, second = result.records
    assert first.date_received == date(2026, 10, 31)
    assert first.product_source == "Credit card"
    assert first.timely_response == "YES"
    assert first.date_sent_to_company == date(2026, 11, 1)
    assert len(first.source_row_fingerprint) == 64
    assert second.timely_response == "UNKNOWN"


def test_validate_rows_preserves_restricted_narrative_only_in_record() -> None:
    schema = resolve_schema(
        ["Complaint ID", "Date received", "Product", "Consumer complaint narrative"]
    )
    result = validate_rows(
        [
            {
                "Complaint ID": "100",
                "Date received": "2026-10-31",
                "Product": "Credit card",
                "Consumer complaint narrative": "Call me at 555-0100",
            }
        ],
        schema=schema,
        snapshot_id="snapshot-001",
    )

    assert result.records[0].narrative_restricted == "Call me at 555-0100"
    assert "555-0100" not in result.records[0].source_row_fingerprint
