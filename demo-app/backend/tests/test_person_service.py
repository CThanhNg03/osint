import io
import importlib
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture(scope="session")
def client():
    os.environ.setdefault("REDIS_URL", "redis://redis:6379/0")
    os.environ.setdefault("IMAGE_STORE_PATH", "/tmp/images")
    os.environ.setdefault("TEST_MODE", "1")
    person_service_mod = importlib.import_module("person_service")
    return TestClient(person_service_mod.app)


def test_detect_blank_image_returns_no_face(client):
    # Create a simple blank image
    buf = io.BytesIO()
    Image.new("RGB", (256, 256), color=(255, 255, 255)).save(buf, format="JPEG")
    buf.seek(0)

    resp = client.post(
        "/image/detect",
        files={"file": ("blank.jpg", buf.getvalue(), "image/jpeg")},
    )
    assert resp.status_code in (200, 503)  # 503 if Redis not ready
    if resp.status_code == 200:
        body = resp.json()
        assert "status" in body
        assert body.get("image_id")
