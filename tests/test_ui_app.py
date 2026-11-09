from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_app_renders_safety_notice_without_runtime_configuration() -> None:
    app_path = Path(__file__).parents[1] / "src" / "pig_finserv" / "ui" / "app.py"

    app = AppTest.from_file(str(app_path)).run()

    assert not app.exception
    assert any("PoC safety notice" in warning.value for warning in app.warning)
