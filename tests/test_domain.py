from datetime import date
from uuid import UUID

import pytest
from typer.testing import CliRunner

from pig_finserv.cli import app
from pig_finserv.domain import (
    ReportPeriodError,
    ReportRequest,
    TriageRequest,
    parse_request_id,
)


def test_cli_exposes_version_subcommand() -> None:
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"


def test_triage_request_normalizes_whitespace_without_mutating_source() -> None:
    request = TriageRequest(narrative="  Duplicate\n\tcharge  ")

    assert request.normalized_narrative() == "Duplicate charge"
    assert request.narrative == "  Duplicate\n\tcharge  "
    assert request.has_usable_narrative()


def test_triage_request_detects_empty_normalized_narrative() -> None:
    assert not TriageRequest(narrative=" \n\t ").has_usable_narrative()


def test_parse_request_id_accepts_uuid_only() -> None:
    request_id = parse_request_id("d78ee0d6-6823-49ad-89de-e0d28f0dcf7f")

    assert request_id == UUID("d78ee0d6-6823-49ad-89de-e0d28f0dcf7f")
    assert parse_request_id(None) is None


def test_parse_request_id_rejects_free_text() -> None:
    with pytest.raises(ValueError, match="UUID"):
        parse_request_id("customer@example.com")


def test_report_allows_zero_volume_as_of_date_inside_coverage() -> None:
    request = ReportRequest(product="Credit card", as_of_date=date(2026, 10, 31))

    request.validate_against_snapshot(
        earliest_date=date(2025, 10, 1),
        latest_completed_date=date(2026, 10, 31),
    )


def test_report_rejects_future_as_of_date() -> None:
    request = ReportRequest(product="Credit card", as_of_date=date(2026, 11, 1))

    with pytest.raises(ReportPeriodError, match="latest completed"):
        request.validate_against_snapshot(
            earliest_date=date(2025, 10, 1),
            latest_completed_date=date(2026, 10, 31),
        )


def test_report_rejects_insufficient_history() -> None:
    request = ReportRequest(product="Credit card", as_of_date=date(2026, 10, 31))

    with pytest.raises(ReportPeriodError, match="historical coverage"):
        request.validate_against_snapshot(
            earliest_date=date(2026, 1, 1),
            latest_completed_date=date(2026, 10, 31),
        )
