import os

os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "test-field-encryption-key")
os.environ.setdefault("WEBHOOK_SIGNING_SECRET", "test-webhook-secret")

from app.main import app


def test_fastapi_application_imports_with_registered_routers() -> None:
    assert app.title
    assert any(route.path == "/health" for route in app.routes)
