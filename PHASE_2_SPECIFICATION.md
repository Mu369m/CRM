# PHASE 2 DETAILED SPECIFICATION

**Target**: Broker Admin Portal Complete  
**Estimated Duration**: 4-5 days (full-time)  
**Estimated LOC**: 2,500+ lines  
**Priority Modules**:
1. RBAC Enforcement (Permission checks)
2. Client Management
3. IB/Affiliate Management
4. Deposits & Withdrawals
5. KYC & Documents
6. Seed Data

---

## MODULE 1: RBAC ENFORCEMENT & ORGANIZATION

### 1.1 Permission Checking Middleware

**File**: `backend/app/middleware/permission_check.py`

```python
# Core permission checking function
async def check_permission(
    user_id: UUID,
    resource: str,  # "leads", "clients", "deposits"
    action: str,    # "create", "view", "edit", "delete", "approve"
    db: AsyncSession,
    tenant_id: UUID,
) -> bool:
    # Get user's roles
    # Get roles' permissions
    # Check if permission exists
    # Return True/False
```

**Permissions to implement**:
```
leads.view
leads.create
leads.edit
leads.delete
leads.export

clients.view
clients.create
clients.edit
clients.delete
clients.export

deposits.view
deposits.create
deposits.approve
deposits.reject
deposits.export

withdrawals.view
withdrawals.create
withdrawals.approve
withdrawals.reject

kyc.view
kyc.approve
kyc.reject

ib.view
ib.create
ib.edit
ib.delete

reports.view
reports.create

settings.manage
users.manage
```

**Integration points**:
- Add to all existing lead endpoints
- Add to new client endpoints
- Add to new deposit/withdrawal endpoints
- Add to new KYC endpoints
- Add to new IB endpoints

**Estimated LOC**: 150 lines

---

### 1.2 Department Management API

**File**: `backend/app/api/v1/broker/departments.py`

**Models** (already exist):
- Department (tenant_id, name, description, manager_id, created_at)

**Endpoints**:
```python
@router.post("/", response_model=DepartmentResponse)
async def create_department(payload: DepartmentCreate, claims: dict, db: AsyncSession):
    """Create department. Requires: settings.manage"""
    
@router.get("/", response_model=List[DepartmentResponse])
async def list_departments(tenant_id: UUID, db: AsyncSession):
    """List all departments"""
    
@router.get("/{dept_id}", response_model=DepartmentResponse)
async def get_department(dept_id: UUID, claims: dict, db: AsyncSession):
    """Get department details with team count"""
    
@router.put("/{dept_id}", response_model=DepartmentResponse)
async def update_department(dept_id: UUID, payload: DepartmentUpdate, claims: dict, db: AsyncSession):
    """Update department. Requires: settings.manage"""
    
@router.delete("/{dept_id}")
async def delete_department(dept_id: UUID, claims: dict, db: AsyncSession):
    """Delete department. Requires: settings.manage"""
```

**Schemas**:
```python
class DepartmentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    manager_id: Optional[UUID] = None

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    manager_id: Optional[UUID] = None

class DepartmentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str]
    manager_id: Optional[UUID]
    team_count: int
    created_at: datetime
    updated_at: datetime
```

**Estimated LOC**: 150 lines

---

### 1.3 Team Management API

**File**: `backend/app/api/v1/broker/teams.py`

**Models** (already exist):
- Team (tenant_id, department_id, name, description, created_at)
- TeamMember (tenant_id, team_id, user_id, role, joined_at)

**Endpoints**:
```python
@router.post("/", response_model=TeamResponse)
async def create_team(payload: TeamCreate, claims: dict, db: AsyncSession):
    """Create team"""
    
@router.get("/", response_model=List[TeamResponse])
async def list_teams(dept_id: Optional[UUID] = None, db: AsyncSession = None):
    """List teams, optionally filter by department"""
    
@router.get("/{team_id}", response_model=TeamResponseWithMembers)
async def get_team(team_id: UUID, claims: dict, db: AsyncSession):
    """Get team with members"""
    
@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(team_id: UUID, payload: TeamUpdate, claims: dict, db: AsyncSession):
    """Update team"""
    
@router.delete("/{team_id}")
async def delete_team(team_id: UUID, claims: dict, db: AsyncSession):
    """Delete team"""

@router.post("/{team_id}/members", response_model=TeamMemberResponse)
async def add_team_member(team_id: UUID, payload: AddTeamMember, claims: dict, db: AsyncSession):
    """Add member to team"""
    
@router.delete("/{team_id}/members/{user_id}")
async def remove_team_member(team_id: UUID, user_id: UUID, claims: dict, db: AsyncSession):
    """Remove member from team"""
```

**Estimated LOC**: 180 lines

---

### 1.4 Role & Permission Management API

**File**: `backend/app/api/v1/broker/roles.py`

**Models** (already exist):
- DynamicRole
- DynamicPermission
- RolePermission

**Endpoints**:
```python
@router.post("/", response_model=DynamicRoleResponse)
async def create_role(payload: CreateRole, claims: dict, db: AsyncSession):
    """Create custom role. Requires: settings.manage"""
    
@router.get("/", response_model=List[DynamicRoleResponse])
async def list_roles(claims: dict, db: AsyncSession):
    """List all roles for tenant"""
    
@router.put("/{role_id}", response_model=DynamicRoleResponse)
async def update_role(role_id: UUID, payload: UpdateRole, claims: dict, db: AsyncSession):
    """Update role"""
    
@router.delete("/{role_id}")
async def delete_role(role_id: UUID, claims: dict, db: AsyncSession):
    """Delete role (cannot delete default roles)"""

@router.get("/{role_id}/permissions", response_model=List[PermissionResponse])
async def get_role_permissions(role_id: UUID, claims: dict, db: AsyncSession):
    """Get permissions for role"""
    
@router.post("/{role_id}/permissions/{permission_id}")
async def grant_permission(role_id: UUID, permission_id: UUID, claims: dict, db: AsyncSession):
    """Grant permission to role"""
    
@router.delete("/{role_id}/permissions/{permission_id}")
async def revoke_permission(role_id: UUID, permission_id: UUID, claims: dict, db: AsyncSession):
    """Revoke permission from role"""

@router.get("/available", response_model=List[PermissionResponse])
async def get_available_permissions(claims: dict, db: AsyncSession):
    """Get all available permissions"""
```

**Estimated LOC**: 200 lines

---

### Summary: Module 1
**Total LOC**: ~680 lines  
**Files**: 4 new API modules  
**Database**: No changes (models already exist)  
**Priority**: CRITICAL - Permission enforcement is security critical

---

## MODULE 2: CLIENT/TRADER MANAGEMENT

### 2.1 Database Extension

**File**: `backend/alembic/versions/0013_client_management.py`

**New Tables**:
```sql
CREATE TABLE clients (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    first_name VARCHAR NOT NULL,
    last_name VARCHAR NOT NULL,
    email VARCHAR UNIQUE NOT NULL,
    phone VARCHAR,
    country VARCHAR,
    
    -- Trading info
    trading_platform VARCHAR,  -- MT5, MT4, etc.
    account_type VARCHAR,      -- Standard, Raw, etc.
    
    -- CRM info
    assigned_user_id UUID,
    source VARCHAR,            -- Direct, IB, Campaign, etc.
    campaign_id UUID,
    ib_partner_id UUID,
    status VARCHAR DEFAULT 'NEW',  -- NEW, ACTIVE, INACTIVE, BANNED
    
    -- Finance
    total_deposits DECIMAL,
    total_withdrawals DECIMAL,
    net_deposits DECIMAL,
    last_deposit_date TIMESTAMP,
    last_withdrawal_date TIMESTAMP,
    
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE SET NULL,
    FOREIGN KEY (ib_partner_id) REFERENCES ib_partners(id) ON DELETE SET NULL
);

CREATE TABLE client_accounts (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    client_id UUID NOT NULL,
    
    account_number VARCHAR NOT NULL,
    platform VARCHAR NOT NULL,  -- MT5, MT4, Crypto Platform, etc.
    server VARCHAR,
    trading_status VARCHAR,  -- Active, Suspended, Closed
    account_balance DECIMAL,
    equity DECIMAL,
    margin DECIMAL,
    free_margin DECIMAL,
    leverage INTEGER,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(tenant_id, account_number),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE TABLE client_financials (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    client_id UUID NOT NULL,
    
    -- Cumulative data
    total_deposits DECIMAL DEFAULT 0,
    total_withdrawals DECIMAL DEFAULT 0,
    net_deposits DECIMAL DEFAULT 0,
    
    -- Trading data
    total_trading_volume DECIMAL DEFAULT 0,
    total_commissions PAID DECIMAL DEFAULT 0,
    total_profit_loss DECIMAL DEFAULT 0,
    
    last_updated TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_clients_tenant_id ON clients(tenant_id);
CREATE INDEX idx_clients_email ON clients(email);
CREATE INDEX idx_clients_status ON clients(status);
CREATE INDEX idx_clients_assigned_user ON clients(assigned_user_id);
CREATE INDEX idx_client_accounts_tenant_client ON client_accounts(tenant_id, client_id);
```

**Estimated LOC**: 120 lines

---

### 2.2 Client Management API

**File**: `backend/app/api/v1/broker/clients.py`

**Endpoints**:
```python
@router.post("/", response_model=ClientResponse)
async def create_client(payload: ClientCreate, claims: dict, db: AsyncSession):
    """Create client. Requires: clients.create"""
    
@router.get("/", response_model=ClientPageResponse)
async def list_clients(
    page: int = 1,
    limit: int = 20,
    search: str = "",
    status: Optional[str] = None,
    country: Optional[str] = None,
    assigned_to_id: Optional[UUID] = None,
    claims: dict = Depends(current_claims),
    db: AsyncSession = Depends(get_tenant_db),
):
    """List clients with pagination and filtering. Requires: clients.view"""
    
@router.get("/{client_id}", response_model=ClientDetailResponse)
async def get_client(client_id: UUID, claims: dict, db: AsyncSession):
    """Get client details with accounts and financials"""
    
@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(client_id: UUID, payload: ClientUpdate, claims: dict, db: AsyncSession):
    """Update client. Requires: clients.edit"""
    
@router.delete("/{client_id}")
async def delete_client(client_id: UUID, claims: dict, db: AsyncSession):
    """Archive client (soft delete). Requires: clients.delete"""

@router.post("/{client_id}/accounts", response_model=ClientAccountResponse)
async def add_client_account(client_id: UUID, payload: AddAccount, claims: dict, db: AsyncSession):
    """Add trading account to client"""
    
@router.get("/{client_id}/accounts", response_model=List[ClientAccountResponse])
async def get_client_accounts(client_id: UUID, claims: dict, db: AsyncSession):
    """Get all accounts for client"""
    
@router.put("/{client_id}/accounts/{account_id}", response_model=ClientAccountResponse)
async def update_client_account(client_id: UUID, account_id: UUID, payload: UpdateAccount, claims: dict, db: AsyncSession):
    """Update account details"""

@router.post("/{client_id}/tasks", response_model=TaskResponse)
async def create_client_task(client_id: UUID, payload: TaskCreate, claims: dict, db: AsyncSession):
    """Create task for client"""
    
@router.get("/{client_id}/tasks", response_model=List[TaskResponse])
async def get_client_tasks(client_id: UUID, claims: dict, db: AsyncSession):
    """Get tasks for client"""

@router.post("/{client_id}/notes", response_model=NoteResponse)
async def add_client_note(client_id: UUID, payload: NoteCreate, claims: dict, db: AsyncSession):
    """Add note to client"""
    
@router.get("/{client_id}/notes", response_model=List[NoteResponse])
async def get_client_notes(client_id: UUID, claims: dict, db: AsyncSession):
    """Get notes for client"""

@router.get("/{client_id}/activities", response_model=List[ActivityResponse])
async def get_client_activities(client_id: UUID, claims: dict, db: AsyncSession):
    """Get activity timeline for client"""
```

**Schemas**:
```python
class ClientCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    country: Optional[str] = None
    trading_platform: Optional[str] = None
    account_type: Optional[str] = None
    source: Optional[str] = None
    campaign_id: Optional[UUID] = None
    ib_partner_id: Optional[UUID] = None

class ClientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = None
    assigned_user_id: Optional[UUID] = None

class ClientDetailResponse(ClientResponse):
    accounts: List[ClientAccountResponse]
    financials: ClientFinancialsResponse
    activity_count: int

class ClientPageResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[ClientResponse]
```

**Estimated LOC**: 350 lines

---

### Summary: Module 2
**Total LOC**: ~470 lines  
**Files**: 1 migration + 1 API module  
**Database**: 3 new tables  
**Priority**: HIGH - Core CRM entity

---

## MODULE 3: IB/AFFILIATE MANAGEMENT

### 3.1 Database Extension

**File**: `backend/alembic/versions/0014_ib_affiliate.py`

**New Tables**:
```sql
CREATE TABLE ib_partners (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    
    code VARCHAR UNIQUE NOT NULL,
    first_name VARCHAR NOT NULL,
    last_name VARCHAR NOT NULL,
    email VARCHAR,
    phone VARCHAR,
    
    parent_ib_id UUID,  -- For hierarchical IBs
    status VARCHAR DEFAULT 'ACTIVE',  -- ACTIVE, SUSPENDED, INACTIVE
    
    commission_type VARCHAR,  -- FIXED, PERCENTAGE, CPA, HYBRID
    commission_value DECIMAL,
    commission_rebate DECIMAL,
    
    total_clients INTEGER DEFAULT 0,
    total_deposits DECIMAL DEFAULT 0,
    total_commissions_paid DECIMAL DEFAULT 0,
    
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_ib_id) REFERENCES ib_partners(id) ON DELETE SET NULL
);

CREATE TABLE ib_relationships (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    ib_partner_id UUID NOT NULL,
    client_id UUID NOT NULL,
    
    assigned_date TIMESTAMP DEFAULT NOW(),
    commission_override DECIMAL,  -- Override default commission
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (ib_partner_id) REFERENCES ib_partners(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE TABLE ib_commissions (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    ib_partner_id UUID NOT NULL,
    
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    
    total_clients INTEGER,
    total_deposits DECIMAL,
    total_volume DECIMAL,
    total_commission_due DECIMAL,
    payment_status VARCHAR,  -- PENDING, PAID, CANCELLED
    paid_date TIMESTAMP,
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (ib_partner_id) REFERENCES ib_partners(id) ON DELETE CASCADE
);
```

**Estimated LOC**: 100 lines

---

### 3.2 IB Management API

**File**: `backend/app/api/v1/broker/ibs.py`

**Endpoints**:
```python
@router.post("/", response_model=IBPartnerResponse)
async def create_ib(payload: CreateIB, claims: dict, db: AsyncSession):
    """Create IB partner"""
    
@router.get("/", response_model=List[IBPartnerResponse])
async def list_ibs(status: Optional[str] = None, claims: dict = None, db: AsyncSession = None):
    """List IB partners"""
    
@router.get("/{ib_id}", response_model=IBPartnerDetailResponse)
async def get_ib(ib_id: UUID, claims: dict, db: AsyncSession):
    """Get IB details with statistics"""
    
@router.put("/{ib_id}", response_model=IBPartnerResponse)
async def update_ib(ib_id: UUID, payload: UpdateIB, claims: dict, db: AsyncSession):
    """Update IB"""
    
@router.delete("/{ib_id}")
async def delete_ib(ib_id: UUID, claims: dict, db: AsyncSession):
    """Archive IB"""

@router.get("/{ib_id}/clients", response_model=List[ClientResponse])
async def get_ib_clients(ib_id: UUID, claims: dict, db: AsyncSession):
    """Get clients assigned to IB"""
    
@router.post("/{ib_id}/clients/{client_id}")
async def assign_client_to_ib(ib_id: UUID, client_id: UUID, claims: dict, db: AsyncSession):
    """Assign client to IB"""

@router.get("/{ib_id}/commissions", response_model=List[IBCommissionResponse])
async def get_ib_commissions(ib_id: UUID, claims: dict, db: AsyncSession):
    """Get commission history"""
    
@router.post("/{ib_id}/commissions", response_model=IBCommissionResponse)
async def create_commission_record(ib_id: UUID, payload: CreateCommission, claims: dict, db: AsyncSession):
    """Create commission record"""

@router.post("/{ib_id}/commission-rules", response_model=CommissionRuleResponse)
async def set_commission_rule(ib_id: UUID, payload: SetCommission, claims: dict, db: AsyncSession):
    """Set custom commission for IB"""
```

**Estimated LOC**: 250 lines

---

### Summary: Module 3
**Total LOC**: ~350 lines  
**Files**: 1 migration + 1 API module  
**Database**: 3 new tables  
**Priority**: HIGH

---

## MODULE 4: DEPOSITS & WITHDRAWALS

### 4.1 Database Extension

**File**: `backend/alembic/versions/0015_deposits_withdrawals.py`

**New Tables**:
```sql
CREATE TABLE payment_methods (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    
    name VARCHAR NOT NULL,  -- Bank Transfer, Crypto, Stripe, etc.
    type VARCHAR,
    is_active BOOLEAN DEFAULT TRUE,
    
    config_json JSONB,  -- API credentials, etc. (encrypted)
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(tenant_id, name),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE TABLE deposits (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    client_id UUID NOT NULL,
    account_id UUID,
    
    amount DECIMAL NOT NULL,
    currency VARCHAR DEFAULT 'USD',
    status VARCHAR DEFAULT 'PENDING',  -- PENDING, APPROVED, REJECTED, CANCELLED, PROCESSING
    
    payment_method_id UUID NOT NULL,
    transaction_id VARCHAR UNIQUE,  -- External reference
    
    notes TEXT,
    created_by_id UUID,
    approved_by_id UUID,
    approved_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES client_accounts(id) ON DELETE SET NULL,
    FOREIGN KEY (payment_method_id) REFERENCES payment_methods(id),
    FOREIGN KEY (created_by_id) REFERENCES users(id),
    FOREIGN KEY (approved_by_id) REFERENCES users(id)
);

CREATE TABLE withdrawals (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    client_id UUID NOT NULL,
    account_id UUID,
    
    amount DECIMAL NOT NULL,
    currency VARCHAR DEFAULT 'USD',
    status VARCHAR DEFAULT 'PENDING',  -- PENDING, APPROVED, REJECTED, PROCESSING, COMPLETED
    
    payment_method_id UUID NOT NULL,
    transaction_id VARCHAR UNIQUE,
    
    notes TEXT,
    created_by_id UUID,
    approved_by_id UUID,
    approved_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES client_accounts(id) ON DELETE SET NULL,
    FOREIGN KEY (payment_method_id) REFERENCES payment_methods(id),
    FOREIGN KEY (created_by_id) REFERENCES users(id),
    FOREIGN KEY (approved_by_id) REFERENCES users(id)
);

-- Indexes
CREATE INDEX idx_deposits_tenant ON deposits(tenant_id);
CREATE INDEX idx_deposits_client ON deposits(client_id);
CREATE INDEX idx_deposits_status ON deposits(status);
CREATE INDEX idx_withdrawals_tenant ON withdrawals(tenant_id);
CREATE INDEX idx_withdrawals_client ON withdrawals(client_id);
CREATE INDEX idx_withdrawals_status ON withdrawals(status);
```

**Estimated LOC**: 130 lines

---

### 4.2 Deposit & Withdrawal APIs

**File**: `backend/app/api/v1/broker/deposits.py`  
**File**: `backend/app/api/v1/broker/withdrawals.py`

**Deposit Endpoints**:
```python
@router.post("/", response_model=DepositResponse)
async def create_deposit(payload: CreateDeposit, claims: dict, db: AsyncSession):
    """Create deposit. Requires: deposits.create"""
    # Auto-log activity
    # Trigger webhooks
    
@router.get("/", response_model=DepositPageResponse)
async def list_deposits(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    client_id: Optional[UUID] = None,
    claims: dict = None,
    db: AsyncSession = None,
):
    """List deposits with filtering. Requires: deposits.view"""
    
@router.get("/{deposit_id}", response_model=DepositResponse)
async def get_deposit(deposit_id: UUID, claims: dict, db: AsyncSession):
    """Get deposit details"""
    
@router.put("/{deposit_id}/approve", response_model=DepositResponse)
async def approve_deposit(deposit_id: UUID, payload: ApproveDeposit, claims: dict, db: AsyncSession):
    """Approve deposit. Requires: deposits.approve"""
    # Log approval
    # Update client financials
    # Send notification
    # Trigger webhook
    
@router.put("/{deposit_id}/reject", response_model=DepositResponse)
async def reject_deposit(deposit_id: UUID, payload: RejectDeposit, claims: dict, db: AsyncSession):
    """Reject deposit. Requires: deposits.approve"""
```

**Withdrawal Endpoints**: Similar pattern

**Estimated LOC**: 400 lines (deposits + withdrawals)

---

### Summary: Module 4
**Total LOC**: ~530 lines  
**Files**: 1 migration + 2 API modules  
**Database**: 2 new tables  
**Priority**: CRITICAL - Financial operations

---

## MODULE 5: KYC & DOCUMENTS

### 5.1 Database Extension

**File**: `backend/alembic/versions/0016_kyc_documents.py`

**New Tables**:
```sql
CREATE TABLE document_types (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    
    name VARCHAR NOT NULL,  -- Passport, ID Card, etc.
    description TEXT,
    is_required BOOLEAN DEFAULT FALSE,
    expiry_days INTEGER,  -- Null = no expiry
    
    UNIQUE(tenant_id, name),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE TABLE kyc_documents (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    client_id UUID NOT NULL,
    document_type_id UUID NOT NULL,
    
    file_path VARCHAR NOT NULL,  -- S3/storage reference
    file_size INTEGER,
    mime_type VARCHAR,
    
    status VARCHAR DEFAULT 'PENDING',  -- PENDING, APPROVED, REJECTED, EXPIRED
    
    submitted_date TIMESTAMP DEFAULT NOW(),
    reviewed_by_id UUID,
    reviewed_date TIMESTAMP,
    rejection_reason TEXT,
    
    expires_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (document_type_id) REFERENCES document_types(id),
    FOREIGN KEY (reviewed_by_id) REFERENCES users(id)
);

CREATE TABLE kyc_approvals (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    client_id UUID NOT NULL,
    
    status VARCHAR DEFAULT 'PENDING',  -- PENDING, APPROVED, REJECTED
    approved_by_id UUID,
    approved_at TIMESTAMP,
    rejection_reason TEXT,
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (approved_by_id) REFERENCES users(id)
);
```

**Estimated LOC**: 100 lines

---

### 5.2 Document Management API

**File**: `backend/app/api/v1/broker/documents.py`

**Endpoints**:
```python
@router.post("/upload", response_model=KYCDocumentResponse)
async def upload_document(
    client_id: UUID,
    document_type_id: UUID,
    file: UploadFile,
    claims: dict,
    db: AsyncSession
):
    """Upload KYC document"""
    # Save to storage (S3/disk)
    # Create database record
    # Log activity
    
@router.get("/{client_id}", response_model=List[KYCDocumentResponse])
async def get_client_documents(client_id: UUID, claims: dict, db: AsyncSession):
    """Get all documents for client"""
    
@router.get("/download/{doc_id}")
async def download_document(doc_id: UUID, claims: dict, db: AsyncSession):
    """Download document (secure)"""
    
@router.put("/{doc_id}/approve", response_model=KYCDocumentResponse)
async def approve_document(doc_id: UUID, payload: ApproveDocument, claims: dict, db: AsyncSession):
    """Approve document. Requires: kyc.approve"""
    
@router.put("/{doc_id}/reject", response_model=KYCDocumentResponse)
async def reject_document(doc_id: UUID, payload: RejectDocument, claims: dict, db: AsyncSession):
    """Reject document. Requires: kyc.reject"""

@router.post("/types/", response_model=DocumentTypeResponse)
async def create_document_type(payload: CreateDocType, claims: dict, db: AsyncSession):
    """Create document type"""
    
@router.get("/types/", response_model=List[DocumentTypeResponse])
async def list_document_types(claims: dict, db: AsyncSession):
    """List document types"""

@router.put("/{client_id}/approve-kyc", response_model=KYCApprovalResponse)
async def approve_kyc(client_id: UUID, payload: ApproveKYC, claims: dict, db: AsyncSession):
    """Approve KYC for client. Requires: kyc.approve"""
    # Update client status
    # Trigger automation
    # Send notification
```

**Estimated LOC**: 200 lines

---

### Summary: Module 5
**Total LOC**: ~300 lines  
**Files**: 1 migration + 1 API module  
**Database**: 3 new tables  
**Priority**: HIGH - Compliance critical

---

## MODULE 6: SEED DATA

### 6.1 Development Seed Script

**File**: `backend/scripts/seed_development_data.py`

**Creates**:
```
Super Admin User

Broker A Configuration:
├── Admin user
├── Sales Manager role
├── Sales Agent role
├── Support role
├── Custom Fields (MT5 Login, Platform, Leverage, Risk Level)
├── Custom Pipeline (New → Contacted → Interested → KYC → Active)
├── 3 Departments (Sales, Support, Finance)
├── Sample leads (10)
└── Sample clients (5)

Broker B Configuration:
├── Admin user
├── Sales role
├── Support role
├── Custom Fields (Trading Account, VIP Level, Sales Agent)
├── Custom Pipeline (New → Qualified → Demo → Funded)
├── Sample leads (10)
└── Sample clients (5)

Demo Data:
├── Sample deposits (various statuses)
├── Sample withdrawals (various statuses)
├── Sample IB partners
├── Sample tasks
├── Sample notes
└── Sample activities
```

**Estimated LOC**: 200 lines

---

## PHASE 2 SUMMARY

| Module | Files | Migration | LOC | Priority | Security |
|--------|-------|-----------|-----|----------|----------|
| RBAC Enforcement | 4 | No | 680 | CRITICAL | ⚠️ YES |
| Clients | 2 | 0013 | 470 | HIGH | No |
| IBs | 2 | 0014 | 350 | HIGH | No |
| Deposits/Withdrawals | 3 | 0015 | 530 | CRITICAL | ⚠️ YES |
| KYC/Documents | 2 | 0016 | 300 | HIGH | ⚠️ YES |
| Seed Data | 1 | No | 200 | MEDIUM | No |
| **TOTAL** | **14** | **4** | **2,530** | - | - |

---

## IMPLEMENTATION ORDER (Phase 2)

### Day 1-2: Foundation
1. Module 1a: Permission enforcement middleware
2. Module 6: Seed data script (for testing)
3. Run migrations 0013-0016

### Day 2-3: Core Entities
4. Module 1b-c: Department & Team APIs
5. Module 2: Client Management API
6. Module 1d: Role/Permission management API

### Day 3-4: Financial
7. Module 4: Deposits/Withdrawals APIs (CRITICAL)
8. Module 5: KYC/Documents API

### Day 4-5: Verification
9. Add permission checks to existing endpoints
10. Test multi-broker isolation
11. Test permission enforcement
12. Load seed data

---

## ACCEPTANCE CRITERIA (Phase 2)

- [ ] All 4 migrations run without errors
- [ ] Permission checks enforce on all endpoints
- [ ] Clients CRUD working with custom fields
- [ ] IBs can have hierarchical relationships
- [ ] Deposits/withdrawals support multiple statuses
- [ ] Document upload and approval workflow working
- [ ] Multi-tenant isolation verified
- [ ] Seed data creates 2 different broker configurations
- [ ] API documentation auto-generated
- [ ] All schemas validated
- [ ] Activity logs created for all changes
- [ ] Pagination works on all list endpoints

---

**Ready to start Phase 2?** Choose a module to begin.

