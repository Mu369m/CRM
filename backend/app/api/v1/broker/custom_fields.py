"""Custom Fields management API for broker customization."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.db_router import get_tenant_db
from app.models import (
    CustomFieldGroup,
    CustomFieldDefinition,
    CustomFieldValue,
    Tenant,
)
from app.security import current_claims

router = APIRouter(prefix="/api/v1/broker/custom-fields", tags=["Custom Fields"])


# ===== Pydantic Schemas =====
class CustomFieldOptionSchema(BaseModel):
    label: str
    value: str


class CustomFieldDefinitionCreate(BaseModel):
    group_id: UUID
    key: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=200)
    field_type: str = Field(..., regex="^(TEXT|NUMBER|CURRENCY|PERCENTAGE|DATE|DATETIME|DROPDOWN|MULTI_SELECT|CHECKBOX|RADIO|PHONE|EMAIL|URL|LONG_TEXT|FILE|IMAGE|COUNTRY|USER_SELECT|IB_SELECT)$")
    description: str | None = None
    is_required: bool = False
    is_searchable: bool = True
    is_filterable: bool = True
    is_sortable: bool = True
    default_value: str | None = None
    validation_rules: dict = Field(default_factory=dict)
    options_json: List[CustomFieldOptionSchema] = Field(default_factory=list)


class CustomFieldDefinitionUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    is_required: bool | None = None
    is_searchable: bool | None = None
    is_filterable: bool | None = None
    is_sortable: bool | None = None
    default_value: str | None = None
    display_order: int | None = None
    validation_rules: dict | None = None
    options_json: List[CustomFieldOptionSchema] | None = None
    is_active: bool | None = None


class CustomFieldDefinitionResponse(BaseModel):
    id: UUID
    key: str
    label: str
    field_type: str
    description: str | None
    is_required: bool
    is_searchable: bool
    is_filterable: bool
    is_sortable: bool
    default_value: str | None
    display_order: int
    validation_rules: dict
    options_json: list
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


class CustomFieldGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    entity_type: str = Field(..., regex="^(LEAD|CLIENT|IB|ACCOUNT|DEPOSIT|WITHDRAWAL|KYC)$")
    display_order: int = 0


class CustomFieldGroupResponse(BaseModel):
    id: UUID
    name: str
    entity_type: str
    display_order: int
    is_active: bool
    created_at: str
    fields: List[CustomFieldDefinitionResponse] = []

    class Config:
        from_attributes = True


class CustomFieldValueCreate(BaseModel):
    entity_id: UUID
    value: str | None = None


class CustomFieldValueResponse(BaseModel):
    id: UUID
    field_id: UUID
    entity_id: UUID
    value: str | None
    updated_at: str

    class Config:
        from_attributes = True


# ===== Endpoints =====
@router.post("/groups", response_model=CustomFieldGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_field_group(
    payload: CustomFieldGroupCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a new custom field group."""
    tenant_id = UUID(claims["tenant_id"])
    
    # Verify group doesn't exist
    result = await db.execute(
        select(CustomFieldGroup).where(
            (CustomFieldGroup.tenant_id == tenant_id)
            & (CustomFieldGroup.name == payload.name)
        )
    )
    if result.scalar():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Group already exists")
    
    group = CustomFieldGroup(
        tenant_id=tenant_id,
        name=payload.name,
        entity_type=payload.entity_type,
        display_order=payload.display_order,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.get("/groups", response_model=List[CustomFieldGroupResponse])
async def list_field_groups(
    entity_type: str = Query(None),
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List all custom field groups for a tenant."""
    tenant_id = UUID(claims["tenant_id"])
    
    query = select(CustomFieldGroup).where(
        CustomFieldGroup.tenant_id == tenant_id
    )
    
    if entity_type:
        query = query.where(CustomFieldGroup.entity_type == entity_type)
    
    query = query.order_by(CustomFieldGroup.display_order)
    result = await db.execute(query)
    groups = result.scalars().all()
    return groups


@router.get("/groups/{group_id}", response_model=CustomFieldGroupResponse)
async def get_field_group(
    group_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get a specific custom field group."""
    tenant_id = UUID(claims["tenant_id"])
    
    result = await db.execute(
        select(CustomFieldGroup).where(
            (CustomFieldGroup.id == group_id)
            & (CustomFieldGroup.tenant_id == tenant_id)
        )
    )
    group = result.scalar()
    
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    return group


@router.post("/groups/{group_id}/fields", response_model=CustomFieldDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_field_definition(
    group_id: UUID,
    payload: CustomFieldDefinitionCreate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Create a new custom field definition."""
    tenant_id = UUID(claims["tenant_id"])
    
    # Verify group exists
    result = await db.execute(
        select(CustomFieldGroup).where(
            (CustomFieldGroup.id == group_id)
            & (CustomFieldGroup.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    # Verify unique key per tenant
    result = await db.execute(
        select(CustomFieldDefinition).where(
            (CustomFieldDefinition.tenant_id == tenant_id)
            & (CustomFieldDefinition.key == payload.key)
        )
    )
    if result.scalar():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Field key already exists")
    
    field = CustomFieldDefinition(
        tenant_id=tenant_id,
        group_id=group_id,
        key=payload.key,
        label=payload.label,
        field_type=payload.field_type,
        description=payload.description,
        is_required=payload.is_required,
        is_searchable=payload.is_searchable,
        is_filterable=payload.is_filterable,
        is_sortable=payload.is_sortable,
        default_value=payload.default_value,
        validation_rules=payload.validation_rules,
        options_json=[opt.dict() for opt in payload.options_json],
    )
    db.add(field)
    await db.commit()
    await db.refresh(field)
    return field


@router.get("/fields/{field_id}", response_model=CustomFieldDefinitionResponse)
async def get_field_definition(
    field_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get a specific custom field definition."""
    tenant_id = UUID(claims["tenant_id"])
    
    result = await db.execute(
        select(CustomFieldDefinition).where(
            (CustomFieldDefinition.id == field_id)
            & (CustomFieldDefinition.tenant_id == tenant_id)
        )
    )
    field = result.scalar()
    
    if not field:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    return field


@router.put("/fields/{field_id}", response_model=CustomFieldDefinitionResponse)
async def update_field_definition(
    field_id: UUID,
    payload: CustomFieldDefinitionUpdate,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Update a custom field definition."""
    tenant_id = UUID(claims["tenant_id"])
    
    result = await db.execute(
        select(CustomFieldDefinition).where(
            (CustomFieldDefinition.id == field_id)
            & (CustomFieldDefinition.tenant_id == tenant_id)
        )
    )
    field = result.scalar()
    
    if not field:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    # Update fields
    update_data = payload.dict(exclude_unset=True)
    if "options_json" in update_data and update_data["options_json"]:
        update_data["options_json"] = [opt.dict() for opt in update_data["options_json"]]
    
    for key, value in update_data.items():
        setattr(field, key, value)
    
    await db.commit()
    await db.refresh(field)
    return field


@router.delete("/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_field_definition(
    field_id: UUID,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete a custom field definition."""
    tenant_id = UUID(claims["tenant_id"])
    
    result = await db.execute(
        select(CustomFieldDefinition).where(
            (CustomFieldDefinition.id == field_id)
            & (CustomFieldDefinition.tenant_id == tenant_id)
        )
    )
    field = result.scalar()
    
    if not field:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    await db.delete(field)
    await db.commit()


@router.post("/values", response_model=CustomFieldValueResponse, status_code=status.HTTP_201_CREATED)
async def set_field_value(
    payload: CustomFieldValueCreate,
    field_id: UUID = Query(...),
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Set a custom field value for an entity."""
    tenant_id = UUID(claims["tenant_id"])
    
    # Verify field exists and belongs to tenant
    result = await db.execute(
        select(CustomFieldDefinition).where(
            (CustomFieldDefinition.id == field_id)
            & (CustomFieldDefinition.tenant_id == tenant_id)
        )
    )
    if not result.scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    
    # Check if value already exists
    result = await db.execute(
        select(CustomFieldValue).where(
            (CustomFieldValue.field_id == field_id)
            & (CustomFieldValue.entity_id == payload.entity_id)
        )
    )
    value_obj = result.scalar()
    
    if value_obj:
        value_obj.value = payload.value
    else:
        value_obj = CustomFieldValue(
            field_id=field_id,
            entity_id=payload.entity_id,
            value=payload.value,
        )
        db.add(value_obj)
    
    await db.commit()
    await db.refresh(value_obj)
    return value_obj


@router.get("/values", response_model=List[CustomFieldValueResponse])
async def get_entity_field_values(
    entity_id: UUID = Query(...),
    field_ids: List[UUID] | None = Query(None),
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Get custom field values for an entity."""
    query = select(CustomFieldValue).where(
        CustomFieldValue.entity_id == entity_id
    )
    
    if field_ids:
        query = query.where(CustomFieldValue.field_id.in_(field_ids))
    
    result = await db.execute(query)
    values = result.scalars().all()
    return values
