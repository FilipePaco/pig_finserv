"""End-to-end proof of the local CLI workflow using only synthetic complaint data."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from pig_finserv.cli import app


def test_cli_runs_ingest_train_triage_and_report_end_to_end(tmp_path: Path) -> None:
    source = tmp_path / "cfpb.csv"
    mappings = tmp_path / "product-mappings.csv"
    aliases = tmp_path / "company-aliases.csv"
    _write_source(source)
    _write_mappings(mappings)
    _write_aliases(aliases)
    runner = CliRunner()
    environment = {"PIG_FINSERV_FINGERPRINT_SALT": "synthetic-test-salt"}

    ingestion = runner.invoke(
        app,
        [
            "ingest",
            str(source),
            str(tmp_path / "data"),
            str(mappings),
            str(aliases),
            "2026.1",
            "2026.1",
        ],
    )
    assert ingestion.exit_code == 0, ingestion.stdout
    snapshot_id = ingestion.stdout.strip()
    parquet = tmp_path / "data" / f"{snapshot_id}.parquet"

    training = runner.invoke(
        app,
        [
            "train",
            str(source),
            str(mappings),
            snapshot_id,
            "2026.1",
            str(tmp_path / "artifacts" / "product-v1"),
            "--minimum-class-support",
            "2",
        ],
        env=environment,
    )
    assert training.exit_code == 0, training.stdout

    triage = runner.invoke(
        app,
        [
            "triage",
            str(tmp_path / "artifacts" / "product-v1"),
            str(tmp_path / "audit.sqlite"),
            "2026.1",
        ],
        input="My card billing fee was charged twice. Email jane@example.com.",
        env=environment,
    )
    assert triage.exit_code == 0, triage.stdout
    decision = json.loads(triage.stdout)
    assert decision["audit_id"].startswith("triage_")
    assert decision["predicted_product"] == "Credit card"

    report = runner.invoke(
        app,
        ["report", str(parquet), "Credit card", "2025-12-01", str(tmp_path / "report")],
    )
    assert report.exit_code == 0, report.stdout
    assert (tmp_path / "report" / "report.md").exists()
    assert (tmp_path / "report" / "daily-complaints.png").exists()
    assert (tmp_path / "report" / "monthly-complaints.png").exists()


def _write_source(path: Path) -> None:
    headers = [
        "Complaint ID",
        "Date received",
        "Product",
        "Company",
        "Company response to consumer",
        "Timely response?",
        "Issue",
        "Consumer complaint narrative",
    ]
    rows: list[dict[str, str]] = []
    for month_offset in range(36):
        year = 2023 + month_offset // 12
        month = month_offset % 12 + 1
        received = date(year, month, 1).isoformat()
        rows.extend(
            (
                {
                    "Complaint ID": f"card-{year}-{month}",
                    "Date received": received,
                    "Product": "Credit card",
                    "Company": "Example Bank",
                    "Company response to consumer": "Closed with explanation",
                    "Timely response?": "Yes",
                    "Issue": "Billing dispute",
                    "Consumer complaint narrative": "credit card billing fee",
                },
                {
                    "Complaint ID": f"mortgage-{year}-{month}",
                    "Date received": received,
                    "Product": "Mortgage",
                    "Company": "Example Bank",
                    "Company response to consumer": "Closed with explanation",
                    "Timely response?": "Yes",
                    "Issue": "Escrow",
                    "Consumer complaint narrative": "mortgage escrow payment",
                },
            )
        )
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _write_mappings(path: Path) -> None:
    path.write_text(
        "effective_start,effective_end,source_product,source_sub_product,canonical_product,rationale,mapping_version\n"
        "2020-01-01,,Credit card,,Credit card,synthetic mapping,2026.1\n"
        "2020-01-01,,Mortgage,,Mortgage,synthetic mapping,2026.1\n"
    )


def _write_aliases(path: Path) -> None:
    path.write_text(
        "company_source,company_canonical,rationale,reviewer,alias_version\n"
        "Example Bank,Example Bank,synthetic mapping,tester,2026.1\n"
    )
