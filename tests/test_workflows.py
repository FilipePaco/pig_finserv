from datetime import date, timedelta
from pathlib import Path

from pig_finserv.analytics import AnalyticsStore
from pig_finserv.data.curated import CuratedComplaint, write_curated_parquet
from pig_finserv.domain import ReportRequest
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
