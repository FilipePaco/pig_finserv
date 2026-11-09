"""Typed, server-owned configuration for the optional local UI."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class UiConfigurationError(ValueError):
    """Raised when a requested UI capability lacks safe local configuration."""


@dataclass(frozen=True, slots=True)
class UiConfiguration:
    """Local paths and secrets read only from the server environment.

    Browser inputs never populate this object. It deliberately exposes only generic
    availability errors so page code cannot disclose local paths or secret state.
    """

    model_artifact_directory: Path | None
    audit_database: Path | None
    taxonomy_version: str | None
    analytics_parquet: Path | None
    output_directory: Path | None
    fingerprint_salt: bytes | None

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> UiConfiguration:
        """Create configuration from a supplied mapping or the process environment."""

        values = environment if environment is not None else os.environ
        return cls(
            model_artifact_directory=_path_value(values, "PIG_FINSERV_MODEL_ARTIFACT_DIR"),
            audit_database=_path_value(values, "PIG_FINSERV_AUDIT_DATABASE"),
            taxonomy_version=_text_value(values, "PIG_FINSERV_TAXONOMY_VERSION"),
            analytics_parquet=_path_value(values, "PIG_FINSERV_ANALYTICS_PARQUET"),
            output_directory=_path_value(values, "PIG_FINSERV_UI_OUTPUT_DIR"),
            fingerprint_salt=_secret_value(values, "PIG_FINSERV_FINGERPRINT_SALT"),
        )

    def require_triage(self) -> tuple[Path, Path, str, bytes]:
        """Return trusted triage dependencies or a generic safe availability error."""

        if (
            self.model_artifact_directory is None
            or self.audit_database is None
            or self.taxonomy_version is None
            or self.fingerprint_salt is None
        ):
            raise UiConfigurationError("Triage is unavailable until local setup is complete.")
        return (
            self.model_artifact_directory,
            self.audit_database,
            self.taxonomy_version,
            self.fingerprint_salt,
        )

    def require_reporting(self) -> tuple[Path, Path]:
        """Return trusted reporting dependencies or a generic safe availability error."""

        if self.analytics_parquet is None or self.output_directory is None:
            raise UiConfigurationError("Insights is unavailable until local setup is complete.")
        return self.analytics_parquet, self.output_directory

    def require_audit(self) -> Path:
        """Return the trusted audit database or a generic safe availability error."""

        if self.audit_database is None:
            raise UiConfigurationError("Audit is unavailable until local setup is complete.")
        return self.audit_database


def _path_value(values: Mapping[str, str], name: str) -> Path | None:
    value = _text_value(values, name)
    return Path(value) if value else None


def _text_value(values: Mapping[str, str], name: str) -> str | None:
    value = values.get(name, "").strip()
    return value or None


def _secret_value(values: Mapping[str, str], name: str) -> bytes | None:
    value = _text_value(values, name)
    return value.encode() if value else None
