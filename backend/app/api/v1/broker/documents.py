"""
KYC & Document management API endpoints.

Handles client document uploads, KYC verification workflows, and compliance tracking.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db import get_tenant_db
from app.security import current_claims
from app.models import (
    DocumentType,
    KYCDocument,
    KYCApproval,
    Client,
    Activity,
)
from app.middleware.permission_check import check_permission

router = APIRouter(prefix="/api/v1/broker/documents", tags=["KYC & Documents"])


# ========== Schemas ==========

class DocumentTypeCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    required_for_kyc: bool = False
    max_file_size_mb: int = Field(default=10, ge=1)
    allowed_formats: str = Field(default="pdf,jpg,png")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "ID Verification",
                "description": "Government-issued ID or passport",
                "required_for_kyc": True,
                "allowed_formats": "pdf,jpg,png"
            }
        }


class KYCDocumentCreate(BaseModel):
    client_id: UUID
    document_type_id: UUID
    file_name: str = Field(..., max_length=255)
    file_path: str = Field(...)
    file_size_bytes: int = Field(..., gt=0)
    mime_type: str = Field(..., max_length=50)

    class Config:
        json_schema_extra = {
            "example": {
                "client_id": "550e8400-e29b-41d4-a716-446655440000",
                "document_type_id": "550e8400-e29b-41d4-a716-446655440001",
                "file_name": "passport.pdf",
                "file_path": "s3://docs/client-123/passport.pdf",
                "file_size_bytes": 2048576,
                "mime_type": "application/pdf"
            }
        }


class ApproveDocument(BaseModel):
    approved_at: Optional[datetime] = None


class RejectDocument(BaseModel):
    rejection_reason: str = Field(..., max_length=500)


class KYCApprovalCreate(BaseModel):
    kyc_level: str = Field(..., description="BASIC, INTERMEDIATE, FULL")
    notes: Optional[str] = None


class ApproveKYC(BaseModel):
    verified_at: Optional[datetime] = None
    notes: Optional[str] = None


class RejectKYC(BaseModel):
    rejection_reason: str = Field(..., max_length=500)


class DocumentTypeResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    required_for_kyc: bool
    max_file_size_mb: int
    allowed_formats: str
    is_active: bool

    class Config:
        from_attributes = True


class KYCDocumentResponse(BaseModel):
    id: UUID
    client_id: UUID
    document_type_id: UUID
    file_name: str
    file_path: str
    status: str
    mime_type: str
    approved_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class KYCDocumentDetailResponse(KYCDocumentResponse):
    file_size_bytes: int
    rejection_reason: Optional[str]
    approved_by: Optional[UUID]
    rejected_by: Optional[UUID]


class KYCApprovalResponse(BaseModel):
    id: UUID
    client_id: UUID
    kyc_level: str
    status: str
    notes: Optional[str]
    verified_at: Optional[datetime]
    rejection_reason: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class KYCDocumentListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[KYCDocumentResponse]


# ========== Document Type Management ==========

@router.post("/types", response_model=DocumentTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_document_type(
    payload: DocumentTypeCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create document type. Requires: settings.manage"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "settings", "manage", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    # Check if name already exists
    result = await db.execute(
        select(DocumentType).where(
            (DocumentType.name == payload.name) & (DocumentType.tenant_id == tenant_id)
        )
    )
    if result.scalar():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document type already exists"
        )
    
    doc_type = DocumentType(
        tenant_id=tenant_id,
        name=payload.name,
        description=payload.description,
        required_for_kyc=payload.required_for_kyc,
        max_file_size_mb=payload.max_file_size_mb,
        allowed_formats=payload.allowed_formats,
    )
    
    db.add(doc_type)
    await db.commit()
    await db.refresh(doc_type)
    
    return doc_type


@router.get("/types", response_model=List[DocumentTypeResponse])
async def list_document_types(
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get all document types for tenant"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    result = await db.execute(
        select(DocumentType).where(DocumentType.tenant_id == tenant_id)
    )
    return result.scalars().all()


# ========== Document Upload & Management ==========

@router.post("/upload", response_model=KYCDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    payload: KYCDocumentCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Upload KYC document. Requires: kyc.create"""
    
    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])
    
    # Check permission
    has_permission = await check_permission(
        user_id, "kyc", "create", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    # Verify client exists
    result = await db.execute(
        select(Client).where(
            (Client.id == payload.client_id) & (Client.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    
    # Verify document type exists
    result = await db.execute(
        select(DocumentType).where(
            (DocumentType.id == payload.document_type_id) & (DocumentType.tenant_id == tenant_id)
        )
    )
    doc_type = result.scalar()
    if not doc_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document type not found")
    
    # Validate file size
    max_bytes = doc_type.max_file_size_mb * 1024 * 1024
    if payload.file_size_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum: {doc_type.max_file_size_mb}MB"
        )
    
    document = KYCDocument(
        tenant_id=tenant_id,
        client_id=payload.client_id,
        document_type_id=payload.document_type_id,
        file_name=payload.file_name,
        file_path=payload.file_path,
        file_size_bytes=payload.file_size_bytes,
        mime_type=payload.mime_type,
        uploaded_by=user_id,
    )
    
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="KYC_DOCUMENT",
        entity_id=document.id,
        activity_type="CREATED",
        description=f"Document uploaded: {payload.file_name}",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()
    
    return document


@router.get("/", response_model=KYCDocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    client_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List KYC documents. Requires: kyc.view"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "kyc", "view", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    query = select(KYCDocument).where(KYCDocument.tenant_id == tenant_id)
    
    if client_id:
        query = query.where(KYCDocument.client_id == client_id)
    
    if status:
        query = query.where(KYCDocument.status == status)
    
    # Count total
    count_result = await db.execute(query)
    total = len(count_result.scalars().all())
    
    # Paginate
    offset = (page - 1) * limit
    query = query.order_by(desc(KYCDocument.created_at)).offset(offset).limit(limit)
    
    result = await db.execute(query)
    documents = result.scalars().all()
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": documents,
    }


@router.get("/{document_id}", response_model=KYCDocumentDetailResponse)
async def get_document(
    document_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get document details. Requires: kyc.view"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "kyc", "view", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(KYCDocument).where(
            (KYCDocument.id == document_id) & (KYCDocument.tenant_id == tenant_id)
        )
    )
    document = result.scalar()
    
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    return document


@router.post("/{document_id}/approve", response_model=KYCDocumentResponse)
async def approve_document(
    document_id: UUID,
    payload: ApproveDocument,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Approve KYC document. Requires: kyc.approve"""
    
    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])
    
    # Check permission
    has_permission = await check_permission(
        user_id, "kyc", "approve", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(KYCDocument).where(
            (KYCDocument.id == document_id) & (KYCDocument.tenant_id == tenant_id)
        )
    )
    document = result.scalar()
    
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    if document.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve document with status: {document.status}"
        )
    
    document.status = "APPROVED"
    document.approved_by = user_id
    document.approved_at = payload.approved_at or datetime.utcnow()
    
    await db.commit()
    await db.refresh(document)
    
    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="KYC_DOCUMENT",
        entity_id=document.id,
        activity_type="APPROVED",
        description=f"Document approved: {document.file_name}",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()
    
    return document


@router.post("/{document_id}/reject", response_model=KYCDocumentResponse)
async def reject_document(
    document_id: UUID,
    payload: RejectDocument,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Reject KYC document. Requires: kyc.reject"""
    
    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])
    
    # Check permission
    has_permission = await check_permission(
        user_id, "kyc", "reject", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(KYCDocument).where(
            (KYCDocument.id == document_id) & (KYCDocument.tenant_id == tenant_id)
        )
    )
    document = result.scalar()
    
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    if document.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject document with status: {document.status}"
        )
    
    document.status = "REJECTED"
    document.rejected_by = user_id
    document.rejection_reason = payload.rejection_reason
    
    await db.commit()
    await db.refresh(document)
    
    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="KYC_DOCUMENT",
        entity_id=document.id,
        activity_type="REJECTED",
        description=f"Document rejected: {payload.rejection_reason}",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()
    
    return document


# ========== KYC Approval Workflow ==========

@router.post("/kyc-approval", response_model=KYCApprovalResponse, status_code=status.HTTP_201_CREATED)
async def create_kyc_approval(
    payload: KYCApprovalCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create KYC approval request. Requires: kyc.create"""
    
    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])
    
    # Check permission
    has_permission = await check_permission(
        user_id, "kyc", "create", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    kyc_approval = KYCApproval(
        tenant_id=tenant_id,
        client_id=payload.client_id if hasattr(payload, 'client_id') else None,
        kyc_level=payload.kyc_level,
        notes=payload.notes,
    )
    
    db.add(kyc_approval)
    await db.commit()
    await db.refresh(kyc_approval)
    
    return kyc_approval


@router.get("/kyc/{client_id}", response_model=List[KYCApprovalResponse])
async def get_client_kyc_status(
    client_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get KYC approval status for client. Requires: kyc.view"""
    
    tenant_id = UUID(claims["tenant_id"])
    
    # Check permission
    has_permission = await check_permission(
        UUID(claims["sub"]), "kyc", "view", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(KYCApproval).where(
            (KYCApproval.client_id == client_id) & (KYCApproval.tenant_id == tenant_id)
        )
    )
    return result.scalars().all()


@router.post("/kyc/{kyc_approval_id}/approve", response_model=KYCApprovalResponse)
async def approve_kyc(
    kyc_approval_id: UUID,
    payload: ApproveKYC,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Approve KYC verification. Requires: kyc.approve"""
    
    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])
    
    # Check permission
    has_permission = await check_permission(
        user_id, "kyc", "approve", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(KYCApproval).where(
            (KYCApproval.id == kyc_approval_id) & (KYCApproval.tenant_id == tenant_id)
        )
    )
    kyc_approval = result.scalar()
    
    if not kyc_approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    kyc_approval.status = "APPROVED"
    kyc_approval.verified_by = user_id
    kyc_approval.verified_at = payload.verified_at or datetime.utcnow()
    if payload.notes:
        kyc_approval.notes = payload.notes
    
    await db.commit()
    await db.refresh(kyc_approval)
    
    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="KYC_APPROVAL",
        entity_id=kyc_approval.id,
        activity_type="APPROVED",
        description=f"KYC {kyc_approval.kyc_level} approved",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()
    
    return kyc_approval


@router.post("/kyc/{kyc_approval_id}/reject", response_model=KYCApprovalResponse)
async def reject_kyc(
    kyc_approval_id: UUID,
    payload: RejectKYC,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Reject KYC verification. Requires: kyc.reject"""
    
    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["sub"])
    
    # Check permission
    has_permission = await check_permission(
        user_id, "kyc", "reject", db, tenant_id
    )
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
    result = await db.execute(
        select(KYCApproval).where(
            (KYCApproval.id == kyc_approval_id) & (KYCApproval.tenant_id == tenant_id)
        )
    )
    kyc_approval = result.scalar()
    
    if not kyc_approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    kyc_approval.status = "REJECTED"
    kyc_approval.rejection_reason = payload.rejection_reason
    
    await db.commit()
    await db.refresh(kyc_approval)
    
    # Log activity
    activity = Activity(
        tenant_id=tenant_id,
        entity_type="KYC_APPROVAL",
        entity_id=kyc_approval.id,
        activity_type="REJECTED",
        description=f"KYC {kyc_approval.kyc_level} rejected: {payload.rejection_reason}",
        user_id=user_id,
    )
    db.add(activity)
    await db.commit()
    
    return kyc_approval
