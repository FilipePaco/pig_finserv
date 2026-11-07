from datetime import date
from pathlib import Path

import pytest

from pig_finserv.data.mapping import (
    CompanyAliasEntry,
    CompanyAliasMapper,
    MappingConfigurationError,
    ProductMappingEntry,
    TaxonomyMapper,
    load_company_aliases,
    load_product_mappings,
)
from pig_finserv.domain import MappingStatus


def test_taxonomy_mapper_uses_effective_dates_and_preserves_unmapped() -> None:
    mapper = TaxonomyMapper(
        (
            ProductMappingEntry(
                effective_start=date(2020, 1, 1),
                effective_end=date(2023, 12, 31),
                source_product="Credit card or prepaid card",
                source_sub_product=None,
                canonical_product="Credit card",
                rationale="Reviewed historical grouping",
                mapping_version="2026.1",
            ),
        )
    )

    mapped = mapper.map_product(
        source_product="Credit card or prepaid card",
        source_sub_product=None,
        received=date(2022, 6, 1),
    )
    unmapped = mapper.map_product(
        source_product="Credit card or prepaid card",
        source_sub_product=None,
        received=date(2024, 1, 1),
    )

    assert mapped.status is MappingStatus.MAPPED
    assert mapped.canonical_product == "Credit card"
    assert unmapped.status is MappingStatus.UNMAPPED
    assert unmapped.canonical_product is None


def test_taxonomy_mapper_marks_conflicting_matches_ambiguous() -> None:
    mapper = TaxonomyMapper(
        (
            ProductMappingEntry(
                date(2020, 1, 1),
                None,
                "Loan",
                None,
                "Mortgage",
                "First reviewed mapping",
                "2026.1",
            ),
            ProductMappingEntry(
                date(2020, 1, 1),
                None,
                "Loan",
                None,
                "Personal loan",
                "Conflicting reviewed mapping fixture",
                "2026.1",
            ),
        )
    )

    result = mapper.map_product(
        source_product="Loan", source_sub_product=None, received=date(2021, 1, 1)
    )

    assert result.status is MappingStatus.AMBIGUOUS
    assert result.canonical_product is None


def test_company_mapper_uses_exact_normalized_aliases_only() -> None:
    mapper = CompanyAliasMapper(
        (
            CompanyAliasEntry(
                company_source="Example Bank, N.A.",
                company_canonical="Example Bank",
                rationale="Reviewed legal entity alias",
                reviewer="data-owner",
                alias_version="2026.1",
            ),
        )
    )

    reviewed = mapper.map_company("  example bank, n.a. ")
    unreviewed = mapper.map_company("Example Bank Holdings")

    assert reviewed.company_canonical == "Example Bank"
    assert reviewed.status == "REVIEWED"
    assert unreviewed.company_canonical == "Example Bank Holdings"
    assert unreviewed.status == "UNREVIEWED"


def test_mapping_loaders_validate_contracts(tmp_path: Path) -> None:
    products = tmp_path / "products.csv"
    products.write_text(
        "effective_start,effective_end,source_product,source_sub_product,canonical_product,"
        "rationale,mapping_version\n"
        "2020-01-01,,Loan,,Mortgage,Reviewed mapping,2026.1\n"
    )
    aliases = tmp_path / "aliases.csv"
    aliases.write_text(
        "company_source,company_canonical,rationale,reviewer,alias_version\n"
        "Example Bank,Example Bank,Reviewed alias,data-owner,2026.1\n"
    )

    product_entries = load_product_mappings(products)
    company_entries = load_company_aliases(aliases)

    assert product_entries[0].canonical_product == "Mortgage"
    assert company_entries[0].company_canonical == "Example Bank"


def test_mapping_loader_rejects_missing_required_columns(tmp_path: Path) -> None:
    source = tmp_path / "products.csv"
    source.write_text("effective_start,source_product\n2020-01-01,Loan\n")

    with pytest.raises(MappingConfigurationError, match="canonical_product"):
        load_product_mappings(source)
