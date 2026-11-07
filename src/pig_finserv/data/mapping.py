"""Reviewed, date-aware taxonomy and company-alias mappings."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pig_finserv.domain import MappingStatus


class MappingConfigurationError(ValueError):
    """Raised when a reviewed mapping file is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class ProductMappingEntry:
    """One reviewed mapping from a historical CFPB label to a canonical product."""

    effective_start: date
    effective_end: date | None
    source_product: str
    source_sub_product: str | None
    canonical_product: str
    rationale: str
    mapping_version: str

    def applies_to(
        self, *, source_product: str, source_sub_product: str | None, received: date
    ) -> bool:
        """Return whether this entry applies to the source values on a received date."""

        if _normalize(source_product) != _normalize(self.source_product):
            return False
        if self.source_sub_product is not None and _normalize(source_sub_product) != _normalize(
            self.source_sub_product
        ):
            return False
        if received < self.effective_start:
            return False
        return self.effective_end is None or received <= self.effective_end


@dataclass(frozen=True, slots=True)
class ProductMappingResult:
    """Product mapping outcome that keeps unmapped and ambiguous states distinct."""

    status: MappingStatus
    canonical_product: str | None
    mapping_version: str | None


@dataclass(frozen=True, slots=True)
class CompanyAliasEntry:
    """A reviewed exact company-name alias."""

    company_source: str
    company_canonical: str
    rationale: str
    reviewer: str
    alias_version: str


@dataclass(frozen=True, slots=True)
class CompanyAliasResult:
    """Company canonicalization result without automatic fuzzy matching."""

    company_canonical: str | None
    status: str
    alias_version: str | None


class TaxonomyMapper:
    """Map historical product labels using only reviewed, date-aware entries."""

    def __init__(self, entries: tuple[ProductMappingEntry, ...]) -> None:
        self._entries = entries

    def map_product(
        self, *, source_product: str | None, source_sub_product: str | None, received: date
    ) -> ProductMappingResult:
        """Return a mapped, unmapped, or ambiguous result without guessing."""

        if source_product is None or not source_product.strip():
            return ProductMappingResult(MappingStatus.UNMAPPED, None, None)
        matches = tuple(
            entry
            for entry in self._entries
            if entry.applies_to(
                source_product=source_product,
                source_sub_product=source_sub_product,
                received=received,
            )
        )
        canonical_products = {entry.canonical_product for entry in matches}
        if not matches:
            return ProductMappingResult(MappingStatus.UNMAPPED, None, None)
        if len(canonical_products) > 1:
            return ProductMappingResult(MappingStatus.AMBIGUOUS, None, None)
        versions = {entry.mapping_version for entry in matches}
        if len(versions) != 1:
            raise MappingConfigurationError(
                "matching product entries must share one mapping version"
            )
        return ProductMappingResult(
            MappingStatus.MAPPED,
            next(iter(canonical_products)),
            next(iter(versions)),
        )


class CompanyAliasMapper:
    """Canonicalize company names through reviewed exact aliases only."""

    def __init__(self, entries: tuple[CompanyAliasEntry, ...]) -> None:
        aliases: dict[str, CompanyAliasEntry] = {}
        for entry in entries:
            normalized = _normalize(entry.company_source)
            if normalized in aliases:
                raise MappingConfigurationError(f"duplicate company alias: {entry.company_source}")
            aliases[normalized] = entry
        self._aliases = aliases

    def map_company(self, company_source: str | None) -> CompanyAliasResult:
        """Return a reviewed canonical name or retain the source name as unreviewed."""

        if company_source is None or not company_source.strip():
            return CompanyAliasResult(None, "MISSING", None)
        entry = self._aliases.get(_normalize(company_source))
        if entry is None:
            return CompanyAliasResult(company_source.strip(), "UNREVIEWED", None)
        return CompanyAliasResult(entry.company_canonical, "REVIEWED", entry.alias_version)


def load_product_mappings(path: Path) -> tuple[ProductMappingEntry, ...]:
    """Load reviewed product mappings from an explicit CSV contract."""

    required = {
        "effective_start",
        "effective_end",
        "source_product",
        "source_sub_product",
        "canonical_product",
        "rationale",
        "mapping_version",
    }
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        _validate_headers(reader.fieldnames, required, path)
        entries = tuple(
            _product_entry(row, row_number) for row_number, row in enumerate(reader, start=2)
        )
    return entries


def load_company_aliases(path: Path) -> tuple[CompanyAliasEntry, ...]:
    """Load reviewed company aliases from an explicit CSV contract."""

    required = {"company_source", "company_canonical", "rationale", "reviewer", "alias_version"}
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        _validate_headers(reader.fieldnames, required, path)
        entries = tuple(
            _company_entry(row, row_number) for row_number, row in enumerate(reader, start=2)
        )
    return entries


def _product_entry(row: dict[str, str | None], row_number: int) -> ProductMappingEntry:
    start = _parse_required_date(row, "effective_start", row_number)
    end_text = _required_text(row, "effective_end", row_number, allow_empty=True)
    end = date.fromisoformat(end_text) if end_text else None
    if end is not None and end < start:
        raise MappingConfigurationError(f"row {row_number}: effective_end precedes effective_start")
    return ProductMappingEntry(
        effective_start=start,
        effective_end=end,
        source_product=_required_text(row, "source_product", row_number),
        source_sub_product=(
            _required_text(row, "source_sub_product", row_number, allow_empty=True) or None
        ),
        canonical_product=_required_text(row, "canonical_product", row_number),
        rationale=_required_text(row, "rationale", row_number),
        mapping_version=_required_text(row, "mapping_version", row_number),
    )


def _company_entry(row: dict[str, str | None], row_number: int) -> CompanyAliasEntry:
    return CompanyAliasEntry(
        company_source=_required_text(row, "company_source", row_number),
        company_canonical=_required_text(row, "company_canonical", row_number),
        rationale=_required_text(row, "rationale", row_number),
        reviewer=_required_text(row, "reviewer", row_number),
        alias_version=_required_text(row, "alias_version", row_number),
    )


def _validate_headers(fieldnames: list[str] | None, required: set[str], path: Path) -> None:
    missing = sorted(required - set(fieldnames or []))
    if missing:
        raise MappingConfigurationError(
            f"{path.name}: missing required columns: {', '.join(missing)}"
        )


def _parse_required_date(row: dict[str, str | None], field: str, row_number: int) -> date:
    try:
        return date.fromisoformat(_required_text(row, field, row_number))
    except ValueError as exc:
        raise MappingConfigurationError(f"row {row_number}: invalid {field}") from exc


def _required_text(
    row: dict[str, str | None], field: str, row_number: int, *, allow_empty: bool = False
) -> str:
    value = (row.get(field) or "").strip()
    if not value and not allow_empty:
        raise MappingConfigurationError(f"row {row_number}: missing {field}")
    return value


def _normalize(value: str | None) -> str:
    return " ".join((value or "").casefold().split())
