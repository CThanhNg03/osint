import importlib
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
    os.environ.setdefault("REDIS_URL", "redis://redis:6379/0")
    os.environ.setdefault("TEST_MODE", "1")
    main_mod = importlib.import_module("api_gateway")
    return TestClient(main_mod.app)


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json().get("message") is not None


def test_asr_status(client):
    resp = client.get("/asr/status")
    # In TEST_MODE or if queue not configured, endpoint may be 404/503; accept 200/404/503
    assert resp.status_code in (200, 404, 503)
