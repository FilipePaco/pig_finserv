"""Domain contracts shared by ingestion, triage, reporting, and audit services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import UUID


class TriageAction(StrEnum):
    """Safe outcomes defined by the triage policy."""

    AUTO_ROUTE = "AUTO_ROUTE"
    HUMAN_REVIEW_LOW_CONFIDENCE = "HUMAN_REVIEW_LOW_CONFIDENCE"
    HUMAN_REVIEW_EMPTY_INPUT = "HUMAN_REVIEW_EMPTY_INPUT"
    HUMAN_REVIEW_GUARDRAIL_FAILURE = "HUMAN_REVIEW_GUARDRAIL_FAILURE"
    HUMAN_REVIEW_SYSTEM_FAILURE = "HUMAN_REVIEW_SYSTEM_FAILURE"
    HUMAN_REVIEW_UNSUPPORTED_CLASS = "HUMAN_REVIEW_UNSUPPORTED_CLASS"
    REJECTED_INVALID_REQUEST = "REJECTED_INVALID_REQUEST"


class MaskingStatus(StrEnum):
    """Whether text passed through the local PII guard successfully."""

    MASKED = "MASKED"
    NOT_REQUIRED = "NOT_REQUIRED"
    NOT_RUN = "NOT_RUN"
    FAILED = "FAILED"


class MappingStatus(StrEnum):
    """Taxonomy mapping states that must remain distinguishable."""

    MAPPED = "MAPPED"
    UNMAPPED = "UNMAPPED"
    AMBIGUOUS = "AMBIGUOUS"


class ReviewOutcome(StrEnum):
    """Allowlisted outcomes for an immutable human-review correction."""

    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"
    UNSUPPORTED = "UNSUPPORTED"


class ReportPeriodError(ValueError):
    """Raised when an as-of date cannot support the requested report windows."""


@dataclass(frozen=True, slots=True)
class TriageRequest:
    """Validated triage request before the PII guard runs.

    The caller correlation ID is optional but, when supplied, must be an opaque UUID.
    Narratives intentionally stay in memory only and are not serialized by this contract.
    """

    narrative: str
    request_id: UUID | None = None

    def normalized_narrative(self) -> str:
        """Return whitespace-normalized text without mutating the original request."""

        return " ".join(self.narrative.split())

    def has_usable_narrative(self) -> bool:
        """Return whether text remains after safe whitespace normalization."""

        return bool(self.normalized_narrative())


@dataclass(frozen=True, slots=True)
class ReportRequest:
    """Validated user-selected report filters before analytics queries run."""

    product: str
    as_of_date: date
    timezone: str = "America/New_York"

    def validate_against_snapshot(
        self,
        *,
        earliest_date: date,
        latest_completed_date: date,
        required_history_days: int = 365,
    ) -> None:
        """Validate that a zero-volume as-of date still has sufficient loaded history.

        Presence of rows on ``as_of_date`` is not required. The snapshot must instead
        contain the complete historical range needed for the 12-month chart.
        """

        if not self.product.strip():
            raise ValueError("product must not be blank")
        if self.as_of_date > latest_completed_date:
            raise ReportPeriodError("as_of_date is after the latest completed snapshot date")
        history_start_ordinal = self.as_of_date.toordinal() - required_history_days
        if history_start_ordinal < earliest_date.toordinal():
            raise ReportPeriodError("snapshot does not contain the required historical coverage")


def parse_request_id(value: str | None) -> UUID | None:
    """Accept only opaque UUID request IDs so caller metadata cannot become free text."""

    if value is None:
        return None
    try:
        return UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("request_id must be a UUID") from exc
