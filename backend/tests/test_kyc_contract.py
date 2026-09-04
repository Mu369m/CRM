import os
from uuid import uuid4

import pytest
from pydantic import ValidationError

os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "test-field-encryption-key")
os.environ.setdefault("WEBHOOK_SIGNING_SECRET", "test-webhook-secret")

from app.api.v1.broker.documents import KYCDocumentCreate
from app.main import app


def _route_contract() -> set[tuple[str, str]]:
    return {
        (route.path, method)
        for route in app.routes
        if hasattr(route, "methods")
        for method in route.methods
    }


def test_kyc_admin_uses_tenant_scoped_document_routes() -> None:
    routes = _route_contract()

    assert ("/api/v1/broker/documents/", "GET") in routes
    assert ("/api/v1/broker/documents/{document_id}/approve", "POST") in routes
    assert ("/api/v1/broker/documents/{document_id}/reject", "POST") in routes
    assert not any(
        path.startswith("/api/v1/broker/kyc-documents") for path, _ in routes
    )


def test_kyc_document_contract_requires_real_file_metadata() -> None:
    payload = KYCDocumentCreate(
        client_id=uuid4(),
        document_type_id=uuid4(),
        file_name="passport.pdf",
        file_path="tenant/client/document/passport.pdf",
        file_size_bytes=2048,
        mime_type="application/pdf",
    )

    assert payload.file_name == "passport.pdf"
    assert payload.file_size_bytes == 2048

    with pytest.raises(ValidationError):
        KYCDocumentCreate(
            client_id=uuid4(),
            document_type_id=uuid4(),
            file_name="empty.pdf",
            file_path="tenant/client/document/empty.pdf",
            file_size_bytes=0,
            mime_type="application/pdf",
        )
