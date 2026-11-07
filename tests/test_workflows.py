from datetime import date, timedelta
from pathlib import Path

from pig_finserv.analytics import AnalyticsStore
from pig_finserv.data.curated import CuratedComplaint, write_curated_parquet
from pig_finserv.domain import ReportRequest
from pig_finserv.integrations import EvidenceSource, ReportCommentary
from pig_finserv.workflows import ReportWorkflow, ReportWorkflowState


def test_report_workflow_validates_coverage_and_renders_terminal_outputs(tmp_path: Path) -> None:
    as_of_date = date(2026, 10, 31)
    records = tuple(
        CuratedComplaint(
            complaint_id=str(index),
            date_received=as_of_date - timedelta(days=index),
            product_source="Credit card",
            product_canonical="Credit card",
            product_mapping_status="MAPPED",
            issue_source="Billing dispute",
            company_source="Example Bank",
            company_canonical="Example Bank",
            company_alias_status="REVIEWED",
            company_response="Closed with explanation",
            timely_response="YES",
            snapshot_id="snapshot",
            source_row_fingerprint=f"{index:064d}",
        )
        for index in range(366)
    )
    parquet = tmp_path / "snapshot.parquet"
    write_curated_parquet(records, parquet)

    result = ReportWorkflow(AnalyticsStore(parquet)).run(
        request=ReportRequest(product="Credit card", as_of_date=as_of_date),
        output_directory=tmp_path / "report",
    )

    assert result.state is ReportWorkflowState.RENDERED
    assert result.markdown_path.exists()
    assert all(path.exists() for path in result.chart_paths)


class _Retriever:
    def retrieve(self, *, product: str, as_of_date: date) -> tuple[EvidenceSource, ...]:
        del product, as_of_date
        return (
            EvidenceSource(
                "source-1",
                "https://www.consumerfinance.gov/example",
                "CFPB",
                date(2026, 10, 1),
                "Example context",
                "Bounded context",
            ),
        )


class _CommentaryClient:
    def generate_report_commentary(self, **kwargs) -> ReportCommentary:
        assert "metric.current_count" in kwargs["metric_ids"]
        return ReportCommentary(
            "Draft",
            ("metric.current_count is available",),
            (),
            ("Scope is limited.",),
            ("source-1",),
        )


def test_report_workflow_integrates_optional_evidence_and_commentary(tmp_path: Path) -> None:
    as_of_date = date(2026, 10, 31)
    records = tuple(
        CuratedComplaint(
            str(index), as_of_date - timedelta(days=index), "Credit card", "Credit card", "MAPPED",
            "Billing dispute", "Example Bank", "Example Bank", "REVIEWED", "Closed", "YES",
            "snapshot", f"{index:064d}"
        )
        for index in range(366)
    )
    parquet = tmp_path / "snapshot.parquet"
    write_curated_parquet(records, parquet)

    result = ReportWorkflow(
        AnalyticsStore(parquet),
        source_retriever=_Retriever(),
        commentary_client=_CommentaryClient(),
    ).run(request=ReportRequest("Credit card", as_of_date), output_directory=tmp_path / "report")

    assert result.evidence_sources[0].source_id == "source-1"
    assert result.commentary is not None
    assert "Example context" in result.markdown_path.read_text()
