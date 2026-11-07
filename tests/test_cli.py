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
