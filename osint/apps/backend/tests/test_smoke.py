"""Smoke test ensuring the FastAPI app can start."""

from apps.backend.src.main import create_app


def test_app_starts():
    app = create_app()
    assert app.title == "OSINT Toolkit"
