"""Command-line entry point.

Commands are added incrementally as their service contracts are implemented.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

import typer

from pig_finserv.analytics import AnalyticsStore
from pig_finserv.audit import AuditStore
from pig_finserv.data.ingestion import ingest_csv
from pig_finserv.data.mapping import (
    CompanyAliasMapper,
    TaxonomyMapper,
    load_company_aliases,
    load_product_mappings,
)
from pig_finserv.domain import ReportRequest, TriageRequest, parse_request_id
from pig_finserv.modeling.artifact import ModelArtifactError, load_model_artifact
from pig_finserv.modeling.dataset import load_masked_training_dataset
from pig_finserv.modeling.split import split_by_month
from pig_finserv.modeling.training import train_and_store
from pig_finserv.safety.pii import PiiMasker
from pig_finserv.triage import TriageService
from pig_finserv.workflows import ReportWorkflow

app = typer.Typer(no_args_is_help=True, help="Pig FinServ complaint triage and insights.")


@app.callback()
def main() -> None:
    """Run the Pig FinServ command-line application."""


@app.command()
def version() -> None:
    """Print the installed application version."""

    from pig_finserv import __version__

    typer.echo(__version__)


@app.command()
def ingest(
    source: Path,
    output_directory: Path,
    product_mappings: Path,
    company_aliases: Path,
    taxonomy_version: str,
    company_alias_version: str,
) -> None:
    """Ingest a CFPB CSV into a curated Parquet snapshot and manifest."""

    result = ingest_csv(
        source_path=source,
        output_directory=output_directory,
        taxonomy_mapper=TaxonomyMapper(load_product_mappings(product_mappings)),
        company_mapper=CompanyAliasMapper(load_company_aliases(company_aliases)),
        taxonomy_version=taxonomy_version,
        company_alias_version=company_alias_version,
    )
    typer.echo(result.snapshot_id)


@app.command()
def report(parquet: Path, product: str, as_of_date: str, output_directory: Path) -> None:
    """Render deterministic metrics, Markdown, and required complaint trend charts."""

    try:
        parsed_date = date.fromisoformat(as_of_date)
    except ValueError as exc:
        raise typer.BadParameter("as_of_date must use YYYY-MM-DD") from exc
    result = ReportWorkflow(AnalyticsStore(parquet)).run(
        request=ReportRequest(product=product, as_of_date=parsed_date),
        output_directory=output_directory,
    )
    typer.echo(result.markdown_path)


@app.command()
def train(
    source: Path,
    product_mappings: Path,
    snapshot_id: str,
    taxonomy_version: str,
    artifact_directory: Path,
    source_revision: str = "unknown",
    minimum_class_support: int = 50,
) -> None:
    """Train local candidates from a restricted CSV without storing narratives."""

    dataset = load_masked_training_dataset(
        source_path=source,
        snapshot_id=snapshot_id,
        taxonomy_mapper=TaxonomyMapper(load_product_mappings(product_mappings)),
        masker=_masker_from_environment(),
    )
    result = train_and_store(
        partitions=split_by_month(dataset.examples),
        snapshot_id=snapshot_id,
        taxonomy_version=taxonomy_version,
        artifact_directory=artifact_directory,
        source_revision=source_revision,
        created_at_utc=datetime.now(UTC).isoformat(),
        minimum_class_support=minimum_class_support,
    )
    typer.echo(result.artifact_directory)


@app.command()
def triage(
    artifact_directory: Path,
    audit_database: Path,
    taxonomy_version: str,
    request_id: str | None = None,
) -> None:
    """Read a narrative from stdin and return a sanitized local triage decision."""

    try:
        artifact = load_model_artifact(
            directory=artifact_directory, taxonomy_version=taxonomy_version
        )
        parsed_request_id = parse_request_id(request_id)
    except (ModelArtifactError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    narrative = typer.get_text_stream("stdin").read()
    service = TriageService(
        masker=_masker_from_environment(),
        classifier=artifact.estimator,
        policy=artifact.threshold_policy,
        class_calibration_support=artifact.model_card.calibration_class_support,
        audit_store=AuditStore(audit_database),
        probabilities_calibrated=True,
        model_version=artifact.model_card.model_id,
        taxonomy_version=artifact.model_card.taxonomy_version,
    )
    result = service.triage(TriageRequest(narrative=narrative, request_id=parsed_request_id))
    typer.echo(
        json.dumps(
            {
                "audit_id": result.audit_id,
                "action": result.action.value,
                "predicted_product": result.predicted_product,
                "confidence": result.confidence,
                "guardrail_status": result.guardrail_status.value,
                "reason_code": result.reason_code,
            },
            sort_keys=True,
        )
    )


@app.command("validate-model")
def validate_model(artifact_directory: Path, taxonomy_version: str) -> None:
    """Verify an existing local model artifact before it serves triage."""

    try:
        artifact = load_model_artifact(
            directory=artifact_directory, taxonomy_version=taxonomy_version
        )
    except ModelArtifactError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(artifact.model_card.model_id)


@app.command("inspect-audit")
def inspect_audit(audit_database: Path, audit_id: str) -> None:
    """Print a sanitized audit event without input fingerprints or caller IDs."""

    event = AuditStore(audit_database).sanitized_event(audit_id)
    if event is None:
        raise typer.BadParameter("audit event was not found")
    typer.echo(json.dumps(event, sort_keys=True))


@app.command("validate-audit")
def validate_audit(audit_database: Path) -> None:
    """Verify the local audit hash chain and print its event count."""

    typer.echo(AuditStore(audit_database).verify_integrity())


def _masker_from_environment() -> PiiMasker:
    salt = os.environ.get("PIG_FINSERV_FINGERPRINT_SALT")
    if not salt:
        raise typer.BadParameter("PIG_FINSERV_FINGERPRINT_SALT must be set locally")
    return PiiMasker(fingerprint_salt=salt.encode())
