import json
from pathlib import Path

from typer.testing import CliRunner

from pig_finserv.cli import app


def test_cli_exposes_version_and_secure_triage_interface() -> None:
    runner = CliRunner()

    version = runner.invoke(app, ["version"])
    triage_help = runner.invoke(app, ["triage", "--help"])

    assert version.exit_code == 0
    assert version.stdout.strip() == "0.1.0"
    assert triage_help.exit_code == 0
    assert "NARRATIVE [OPTIONS]" not in triage_help.stdout
    assert "stdin" in triage_help.stdout.lower()


def test_invalid_cli_request_id_creates_a_safe_audit_event(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "triage",
            str(tmp_path / "unused-artifact"),
            str(tmp_path / "audit.sqlite"),
            "2026.1",
            "--request-id",
            "free-text-is-not-allowed",
        ],
    )

    response = json.loads(result.stdout)
    assert result.exit_code == 0
    assert response["action"] == "REJECTED_INVALID_REQUEST"
    assert response["audit_id"].startswith("triage_")


def test_smoke_gemini_requires_local_configuration() -> None:
    result = CliRunner().invoke(app, ["smoke-gemini"])

    assert result.exit_code == 2
