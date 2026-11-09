"""Narrow UI adapters to existing safe application workflows."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from pig_finserv.analytics import AnalyticsStore
from pig_finserv.audit import AuditIntegrityError, AuditStore
from pig_finserv.domain import ReportRequest, ReviewOutcome, TriageRequest
from pig_finserv.integrations import CfpbNewsRetriever, GeminiCommentaryClient
from pig_finserv.modeling.artifact import ModelArtifactError, load_model_artifact
from pig_finserv.safety.pii import PiiMasker
from pig_finserv.triage import TriageResult, TriageService
from pig_finserv.ui.configuration import UiConfiguration, UiConfigurationError
from pig_finserv.workflows import ReportWorkflow, ReportWorkflowResult


class UiOperationError(RuntimeError):
    """A generic, browser-safe failure from a local UI operation."""


class UiServices:
    """Use typed core services without accepting paths or commands from the browser."""

    def __init__(self, configuration: UiConfiguration) -> None:
        self._configuration = configuration

    def triage(self, narrative: str) -> TriageResult:
        """Run the existing local triage state machine for an in-memory narrative."""

        artifact_directory, audit_database, taxonomy_version, fingerprint_salt = (
            self._configuration.require_triage()
        )
        try:
            artifact = load_model_artifact(
                directory=artifact_directory, taxonomy_version=taxonomy_version
            )
            service = TriageService(
                masker=PiiMasker(fingerprint_salt=fingerprint_salt),
                classifier=artifact.estimator,
                policy=artifact.threshold_policy,
                class_calibration_support=artifact.model_card.calibration_class_support,
                audit_store=AuditStore(audit_database),
                probabilities_calibrated=True,
                model_version=artifact.model_card.model_id,
                taxonomy_version=artifact.model_card.taxonomy_version,
            )
            return service.triage(TriageRequest(narrative=narrative))
        except (ModelArtifactError, OSError, ValueError) as exc:
            raise UiOperationError("Triage could not access its local dependencies.") from exc

    def report_products(self) -> tuple[str, ...]:
        """Return canonical selector values from the configured analytics snapshot."""

        analytics = self._analytics_store()
        try:
            return analytics.canonical_products()
        except (OSError, ValueError) as exc:
            raise UiOperationError("Insights could not access the local snapshot.") from exc

    def report_bounds(self) -> tuple[date, date]:
        """Return safe date bounds for the report selector."""

        analytics = self._analytics_store()
        try:
            return analytics.coverage_dates()
        except (OSError, ValueError) as exc:
            raise UiOperationError("Insights could not access the local snapshot.") from exc

    def report(
        self, *, product: str, as_of_date: date, include_external_context: bool
    ) -> ReportWorkflowResult:
        """Render an existing facts-first report into a generated server-owned directory."""

        parquet, output_root = self._configuration.require_reporting()
        output_directory = output_root / f"request-{uuid4()}"
        try:
            return ReportWorkflow(
                AnalyticsStore(parquet),
                source_retriever=CfpbNewsRetriever() if include_external_context else None,
                commentary_client=(
                    GeminiCommentaryClient.from_environment() if include_external_context else None
                ),
            ).run(
                request=ReportRequest(product=product, as_of_date=as_of_date),
                output_directory=output_directory,
            )
        except (OSError, ValueError) as exc:
            raise UiOperationError("Insights could not render the requested report.") from exc

    def append_review(
        self,
        *,
        audit_id: str,
        corrected_product: str,
        corrected_issue: str | None,
        outcome: ReviewOutcome,
        reason_code: str,
    ) -> str:
        """Append a human correction using the existing immutable audit contract."""

        try:
            event = AuditStore(self._configuration.require_audit()).append_review(
                parent_audit_id=audit_id,
                corrected_product=corrected_product,
                corrected_issue=corrected_issue,
                outcome=outcome,
                reason_code=reason_code,
            )
            return event.audit_id
        except (OSError, UiConfigurationError, ValueError) as exc:
            raise UiOperationError("Review could not be recorded.") from exc

    def audit_event(self, audit_id: str) -> dict[str, object] | None:
        """Read an existing sanitised audit event."""

        try:
            return AuditStore(self._configuration.require_audit()).sanitized_event(audit_id)
        except (OSError, UiConfigurationError, ValueError) as exc:
            raise UiOperationError("Audit could not be accessed.") from exc

    def verify_audit(self) -> int:
        """Verify the local audit chain without returning audit rows."""

        try:
            return AuditStore(self._configuration.require_audit()).verify_integrity()
        except (AuditIntegrityError, OSError, UiConfigurationError, ValueError) as exc:
            raise UiOperationError("Audit integrity could not be verified.") from exc

    def _analytics_store(self) -> AnalyticsStore:
        parquet, _ = self._configuration.require_reporting()
        return AnalyticsStore(parquet)
