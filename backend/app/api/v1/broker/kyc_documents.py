"""
KYC Documents Management API Endpoints
Handles KYC document uploads, verification, and compliance tracking
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_
from typing import Optional

from app.db import get_db
from app.models.master import KYCDocument
from app.middleware.rbac_enforcer import require_permission
from app.middleware.audit_logger import AuditLogger
from app.security import get_current_user
from app.schemas import (
    KYCDocumentCreate,
    KYCDocumentResponse,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/v1/broker/kyc-documents", tags=["KYC Documents"])


@router.get("", response_model=PaginatedResponse[KYCDocumentResponse])
async def list_kyc_documents(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str = Query("ALL"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(require_permission("kyc.view")),
):
    """List KYC documents with filters"""
    query = select(KYCDocument).where(KYCDocument.broker_id == current_user.broker_id)

    if status != "ALL":
        query = query.where(KYCDocument.status == status)

    # Get total
    count_query = select(func.count()).select_from(KYCDocument)
    count_query = count_query.where(query.whereclause)
    result = await db.execute(count_query)
    total = result.scalar()

    # Get paginated results
    query = query.order_by(desc(KYCDocument.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    documents = result.scalars().all()

    return {
        "items": [KYCDocumentResponse.from_orm(d) for d in documents],
        "total": total,
    }


@router.post("", response_model=KYCDocumentResponse)
async def create_kyc_document(
    data: KYCDocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(require_permission("kyc.upload")),
):
    """Upload new KYC document"""
    document = KYCDocument(
        broker_id=current_user.broker_id,
        client_id=data.client_id,
        document_type=data.document_type,
        file_name=data.file_url.split("/")[-1] if data.file_url else "document",
        file_url=data.file_url,
        status="PENDING",
    )

    db.add(document)
    await db.flush()

    await AuditLogger.log_create(
        db,
        "KYCDocument",
        document.id,
        {
            "client": data.client_id,
            "doc_type": data.document_type,
            "file": document.file_name,
        },
    )

    await db.commit()
    return KYCDocumentResponse.from_orm(document)


@router.get("/{document_id}", response_model=KYCDocumentResponse)
async def get_kyc_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(require_permission("kyc.view")),
):
    """Get single KYC document"""
    result = await db.execute(
        select(KYCDocument).where(
            and_(
                KYCDocument.id == document_id,
                KYCDocument.broker_id == current_user.broker_id,
            )
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return KYCDocumentResponse.from_orm(document)


@router.post("/{document_id}/verify")
async def verify_kyc_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(require_permission("kyc.approve")),
):
    """Verify KYC document"""
    result = await db.execute(
        select(KYCDocument).where(
            and_(
                KYCDocument.id == document_id,
                KYCDocument.broker_id == current_user.broker_id,
            )
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    document.status = "VERIFIED"
    document.verified_by = current_user.id

    await AuditLogger.log_approval(
        db, "KYCDocument", document_id, "verify", {"status": "VERIFIED"}
    )

    await db.commit()

    return {"id": document.id, "status": "VERIFIED", "message": "Document verified"}


@router.post("/{document_id}/reject")
async def reject_kyc_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(require_permission("kyc.reject")),
):
    """Reject KYC document"""
    result = await db.execute(
        select(KYCDocument).where(
            and_(
                KYCDocument.id == document_id,
                KYCDocument.broker_id == current_user.broker_id,
            )
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    document.status = "REJECTED"
    document.verified_by = current_user.id

    await AuditLogger.log_approval(
        db, "KYCDocument", document_id, "reject", {"status": "REJECTED"}
    )

    await db.commit()

    return {"id": document.id, "status": "REJECTED", "message": "Document rejected"}
