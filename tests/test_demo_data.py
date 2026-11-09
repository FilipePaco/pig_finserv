from datetime import date
from pathlib import Path
from runpy import run_path

from pig_finserv.analytics import AnalyticsStore
from pig_finserv.data.ingestion import ingest_csv
from pig_finserv.data.mapping import (
    CompanyAliasMapper,
    TaxonomyMapper,
    load_company_aliases,
    load_product_mappings,
)

create_demo_data = run_path(
    str(Path(__file__).parents[1] / "scripts" / "generate_demo_data.py")
)["create_demo_data"]


def test_interview_demo_has_the_documented_credit_card_signal(tmp_path: Path) -> None:
    create_demo_data(tmp_path)
    result = ingest_csv(
        source_path=tmp_path / "cfpb-demo.csv",
        output_directory=tmp_path / "data",
        taxonomy_mapper=TaxonomyMapper(load_product_mappings(tmp_path / "product-mappings.csv")),
        company_mapper=CompanyAliasMapper(load_company_aliases(tmp_path / "company-aliases.csv")),
        taxonomy_version="2026.1",
        company_alias_version="2026.1",
    )

    metrics = AnalyticsStore(result.parquet_path).report_metrics(
        product="Credit card", as_of_date=date(2025, 12, 1)
    )

    assert (metrics.current_count, metrics.previous_count) == (120, 40)
    assert (metrics.timely_yes_count, metrics.timely_known_count) == (86, 120)
    assert metrics.top_issues[0] == ("Duplicate charge", 75)
    assert metrics.top_companies[0] == ("Northstar Bank", 70)
