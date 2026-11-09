import pytest

from pig_finserv.ui.configuration import UiConfiguration, UiConfigurationError


def test_configuration_requires_complete_triage_setup_without_disclosing_values() -> None:
    configuration = UiConfiguration.from_environment({"PIG_FINSERV_MODEL_ARTIFACT_DIR": "/secret"})

    with pytest.raises(UiConfigurationError) as exc_info:
        configuration.require_triage()

    assert "/secret" not in str(exc_info.value)
    assert "Triage is unavailable" in str(exc_info.value)


def test_configuration_reads_only_server_owned_values() -> None:
    configuration = UiConfiguration.from_environment(
        {
            "PIG_FINSERV_MODEL_ARTIFACT_DIR": "/runtime/model",
            "PIG_FINSERV_AUDIT_DATABASE": "/runtime/audit.sqlite",
            "PIG_FINSERV_TAXONOMY_VERSION": "2026.1",
            "PIG_FINSERV_ANALYTICS_PARQUET": "/runtime/curated.parquet",
            "PIG_FINSERV_UI_OUTPUT_DIR": "/runtime/reports",
            "PIG_FINSERV_FINGERPRINT_SALT": "local-only",
        }
    )

    model_directory, audit_database, taxonomy_version, salt = configuration.require_triage()

    assert str(model_directory) == "/runtime/model"
    assert str(audit_database) == "/runtime/audit.sqlite"
    assert taxonomy_version == "2026.1"
    assert salt == b"local-only"
    assert configuration.require_reporting()[0].name == "curated.parquet"
