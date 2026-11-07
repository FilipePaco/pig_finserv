"""Explicit, bounded application workflow state machines."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pig_finserv.analytics import AnalyticsStore, ReportMetrics
from pig_finserv.charts import render_report_charts
from pig_finserv.domain import ReportRequest
from pig_finserv.integrations import (
    CfpbNewsRetriever,
    EvidenceSource,
    GeminiCommentaryClient,
    ProviderUnavailableError,
    ReportCommentary,
)
from pig_finserv.reporting import render_markdown


class ReportWorkflowState(StrEnum):
    """Monotonic states for the deterministic report workflow."""

    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    METRICS_READY = "METRICS_READY"
    RENDERED = "RENDERED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ReportWorkflowResult:
    """Terminal report state with deterministic output paths."""

    state: ReportWorkflowState
    metrics: ReportMetrics
    markdown_path: Path
    chart_paths: tuple[Path, Path]
    evidence_sources: tuple[EvidenceSource, ...]
    commentary: ReportCommentary | None


class ReportWorkflow:
    """Run fixed validation, metrics, chart, and rendering transitions locally."""

    def __init__(
        self,
        analytics_store: AnalyticsStore,
        *,
        source_retriever: CfpbNewsRetriever | None = None,
        commentary_client: GeminiCommentaryClient | None = None,
    ) -> None:
        self._analytics_store = analytics_store
        self._source_retriever = source_retriever
        self._commentary_client = commentary_client

    def run(self, *, request: ReportRequest, output_directory: Path) -> ReportWorkflowResult:
        """Render facts-first report outputs or propagate a typed validation error."""

        self._validate(request)
        metrics = self._analytics_store.report_metrics(
            product=request.product, as_of_date=request.as_of_date
        )
        sources = (
            self._source_retriever.retrieve(product=request.product, as_of_date=request.as_of_date)
            if self._source_retriever
            else ()
        )
        commentary = self._commentary(metrics, sources)
        output_directory.mkdir(parents=True, exist_ok=True)
        markdown_path = output_directory / "report.md"
        markdown_path.write_text(
            render_markdown(
                metrics,
                evidence_sources=sources,
                commentary=commentary,
                timezone=request.timezone,
            )
        )
        chart_paths = render_report_charts(metrics, output_directory)
        return ReportWorkflowResult(
            state=ReportWorkflowState.RENDERED,
            metrics=metrics,
            markdown_path=markdown_path,
            chart_paths=chart_paths,
            evidence_sources=sources,
            commentary=commentary,
        )

    def _validate(self, request: ReportRequest) -> None:
        earliest, latest = self._analytics_store.coverage_dates()
        request.validate_against_snapshot(
            earliest_date=earliest,
            latest_completed_date=latest,
        )

    def _commentary(
        self, metrics: ReportMetrics, sources: tuple[EvidenceSource, ...]
    ) -> ReportCommentary | None:
        if self._commentary_client is None:
            return None
        try:
            return self._commentary_client.generate_report_commentary(
                safe_payload={
                    "metric.current_count": metrics.current_count,
                    "metric.previous_count": metrics.previous_count,
                    "metric.timely_response_rate": metrics.timely_response_rate,
                    "product": metrics.product,
                    "sources": [
                        {"source_id": source.source_id, "title": source.title}
                        for source in sources
                    ],
                },
                metric_ids=frozenset(
                    {
                        "metric.current_count",
                        "metric.previous_count",
                        "metric.timely_response_rate",
                    }
                ),
                source_ids=frozenset(source.source_id for source in sources),
            )
        except ProviderUnavailableError:
            return None
