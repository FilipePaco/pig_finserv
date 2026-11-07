"""CFPB source-schema adaptation and deterministic row validation."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime


class SchemaValidationError(ValueError):
    """Raised when a required CFPB source column cannot be resolved."""


REQUIRED_FIELDS = frozenset({"complaint_id", "date_received", "product_source"})

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "complaint_id": ("Complaint ID", "complaint_id"),
    "date_received": ("Date received", "date_received"),
    "product_source": ("Product", "product"),
    "sub_product_source": ("Sub-product", "sub_product"),
    "issue_source": ("Issue", "issue"),
    "sub_issue_source": ("Sub-issue", "sub_issue"),
    "company_source": ("Company", "company"),
    "company_response": ("Company response to consumer", "company_response_to_consumer"),
    "timely_response": ("Timely response?", "timely_response"),
    "date_sent_to_company": ("Date sent to company", "date_sent_to_company"),
    "submitted_via": ("Submitted via", "submitted_via"),
    "narrative_restricted": (
        "Consumer complaint narrative",
        "Complaint narrative",
        "complaint_what_happened",
    ),
}


@dataclass(frozen=True, slots=True)
class SourceSchema:
    """Resolved mapping from canonical fields to observed source columns."""

    columns: dict[str, str]

    def source_column(self, canonical_field: str) -> str | None:
        """Return the observed source column for a canonical field when available."""

        return self.columns.get(canonical_field)


@dataclass(frozen=True, slots=True)
class ComplaintRecord:
    """Validated, source-preserving complaint row before taxonomy mapping."""

    complaint_id: str
    date_received: date
    product_source: str
    sub_product_source: str | None
    issue_source: str | None
    sub_issue_source: str | None
    company_source: str | None
    company_response: str | None
    timely_response: str
    date_sent_to_company: date | None
    submitted_via: str | None
    narrative_restricted: str | None
    source_row_fingerprint: str
    snapshot_id: str


@dataclass(frozen=True, slots=True)
class RejectedRow:
    """Safe row-level rejection metadata without raw source values."""

    row_number: int
    reason: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Validated records plus deterministic quality counters."""

    records: tuple[ComplaintRecord, ...]
    duplicates: int
    rejected_rows: tuple[RejectedRow, ...]

    @property
    def rejection_counts(self) -> dict[str, int]:
        """Return rejection reasons in deterministic lexical order."""

        counts = Counter(row.reason for row in self.rejected_rows)
        return dict(sorted(counts.items()))


def resolve_schema(headers: Iterable[str]) -> SourceSchema:
    """Resolve documented CFPB aliases and fail clearly when required fields are absent."""

    available = set(headers)
    columns: dict[str, str] = {}
    for canonical_field, aliases in FIELD_ALIASES.items():
        match = next((alias for alias in aliases if alias in available), None)
        if match is not None:
            columns[canonical_field] = match

    missing = sorted(REQUIRED_FIELDS - columns.keys())
    if missing:
        raise SchemaValidationError(
            "Missing required CFPB fields: "
            + ", ".join(missing)
            + ". Observed columns must include documented aliases."
        )
    return SourceSchema(columns=columns)


def validate_rows(
    rows: Iterable[Mapping[str, str | None]],
    *,
    schema: SourceSchema,
    snapshot_id: str,
) -> ValidationResult:
    """Validate source rows, retaining the first deterministic complaint ID occurrence."""

    records: list[ComplaintRecord] = []
    rejected: list[RejectedRow] = []
    seen_complaint_ids: set[str] = set()
    duplicates = 0

    for row_number, row in enumerate(rows, start=2):
        try:
            record = _to_record(row, schema=schema, snapshot_id=snapshot_id)
        except ValueError as exc:
            rejected.append(RejectedRow(row_number=row_number, reason=str(exc)))
            continue

        if record.complaint_id in seen_complaint_ids:
            duplicates += 1
            continue
        seen_complaint_ids.add(record.complaint_id)
        records.append(record)

    return ValidationResult(
        records=tuple(records), duplicates=duplicates, rejected_rows=tuple(rejected)
    )


def _to_record(
    row: Mapping[str, str | None], *, schema: SourceSchema, snapshot_id: str
) -> ComplaintRecord:
    complaint_id = _required_value(row, schema, "complaint_id")
    date_received = _parse_required_date(row, schema, "date_received")
    product_source = _required_value(row, schema, "product_source")
    issue_source = _optional_value(row, schema, "issue_source")
    company_source = _optional_value(row, schema, "company_source")

    fingerprint_fields = {
        "complaint_id": complaint_id,
        "date_received": date_received.isoformat(),
        "product_source": product_source,
        "issue_source": issue_source,
        "company_source": company_source,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_fields, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    return ComplaintRecord(
        complaint_id=complaint_id,
        date_received=date_received,
        product_source=product_source,
        sub_product_source=_optional_value(row, schema, "sub_product_source"),
        issue_source=issue_source,
        sub_issue_source=_optional_value(row, schema, "sub_issue_source"),
        company_source=company_source,
        company_response=_optional_value(row, schema, "company_response"),
        timely_response=_normalize_timely_response(_optional_value(row, schema, "timely_response")),
        date_sent_to_company=_parse_optional_date(row, schema, "date_sent_to_company"),
        submitted_via=_optional_value(row, schema, "submitted_via"),
        narrative_restricted=_optional_value(row, schema, "narrative_restricted"),
        source_row_fingerprint=fingerprint,
        snapshot_id=snapshot_id,
    )


def _required_value(row: Mapping[str, str | None], schema: SourceSchema, field: str) -> str:
    value = _optional_value(row, schema, field)
    if value is None:
        raise ValueError(f"MISSING_{field.upper()}")
    return value


def _optional_value(
    row: Mapping[str, str | None], schema: SourceSchema, field: str
) -> str | None:
    source_column = schema.source_column(field)
    if source_column is None:
        return None
    value = row.get(source_column)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _parse_required_date(row: Mapping[str, str | None], schema: SourceSchema, field: str) -> date:
    value = _optional_value(row, schema, field)
    if value is None:
        raise ValueError(f"MISSING_{field.upper()}")
    try:
        return _parse_date(value)
    except ValueError as exc:
        raise ValueError(f"INVALID_{field.upper()}") from exc


def _parse_optional_date(
    row: Mapping[str, str | None], schema: SourceSchema, field: str
) -> date | None:
    value = _optional_value(row, schema, field)
    if value is None:
        return None
    try:
        return _parse_date(value)
    except ValueError:
        return None


def _parse_date(value: str) -> date:
    for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _normalize_timely_response(value: str | None) -> str:
    if value is None:
        return "UNKNOWN"
    normalized = value.upper()
    if normalized in {"YES", "NO"}:
        return normalized
    return "UNKNOWN"
