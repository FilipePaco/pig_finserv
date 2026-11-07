"""Command-line entry point.

Commands are added incrementally as their service contracts are implemented.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer

from pig_finserv.analytics import AnalyticsStore
from pig_finserv.charts import render_report_charts
from pig_finserv.data.ingestion import ingest_csv
from pig_finserv.data.mapping import (
    CompanyAliasMapper,
    TaxonomyMapper,
    load_company_aliases,
    load_product_mappings,
)
from pig_finserv.reporting import render_markdown

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
    metrics = AnalyticsStore(parquet).report_metrics(product=product, as_of_date=parsed_date)
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "report.md").write_text(render_markdown(metrics))
    render_report_charts(metrics, output_directory)
    typer.echo(output_directory / "report.md")
