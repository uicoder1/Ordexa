from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Auth & User ---
class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    password: str
    company_name: Optional[str] = None

class UserResponse(UserBase):
    id: str
    created_at: datetime
    is_platform_admin: bool = False
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    active_organization_id: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

# --- Organization ---
class OrganizationCreate(BaseModel):
    name: str
    sales_channels: Optional[str] = "Amazon,Flipkart,Shopify"

class OrganizationResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    sales_channels: str
    role: Optional[str] = "owner"
    created_at: datetime
    class Config:
        from_attributes = True


# --- Product ---
class ProductCreate(BaseModel):
    sku: str
    product_name: str
    category: Optional[str] = "General"
    purchase_cost: float
    selling_price: Optional[float] = 0.0
    marketplace: Optional[str] = "All"

class ProductUpdate(BaseModel):
    product_name: Optional[str] = None
    category: Optional[str] = None
    purchase_cost: Optional[float] = None
    selling_price: Optional[float] = None
    marketplace: Optional[str] = None

class ProductResponse(ProductCreate):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True


# --- Upload & Mapping ---
class ColumnMappingRequest(BaseModel):
    upload_id: str
    marketplace: str
    mapping: Dict[str, str] # e.g. {"Seller SKU": "sku", "Order Id": "order_id", ...}
    deduplication_mode: Optional[str] = "skip" # skip, replace, import_all

class UploadedFileResponse(BaseModel):
    id: str
    organization_id: str
    filename: str
    marketplace: str
    storage_path: str
    file_type: str
    file_size: int
    upload_status: str
    rows_processed: int
    rows_failed: int
    column_mapping: Optional[str] = None
    error_message: Optional[str] = None
    uploaded_at: datetime
    class Config:
        from_attributes = True


# --- SKU Metrics & Dashboard ---
class SKUMetricResponse(BaseModel):
    id: str
    organization_id: str
    sku: str
    product_name: Optional[str] = "N/A"
    category: Optional[str] = "General"
    purchase_cost: float = 0.0
    period_name: str
    total_orders: int
    units_sold: int
    revenue: float
    returns_count: int
    return_rate: float
    rto_count: int
    rto_rate: float
    total_product_cost: float
    marketplace_fees: float
    shipping_cost: float
    return_cost: float
    refund_amount: float
    net_settlement: float
    actual_profit: float
    profit_margin: float
    profit_leakage: float
    risk_level: str
    recommended_action: str
    calculated_at: datetime
    class Config:
        from_attributes = True

class DashboardSummaryResponse(BaseModel):
    total_revenue: float
    net_settlement: float
    actual_profit: float
    profit_margin: float
    total_orders: int
    total_units_sold: int
    return_rate: float
    rto_rate: float
    total_skus: int
    critical_skus_count: int
    warning_skus_count: int
    healthy_skus_count: int
    period_comparison: str = "vs previous period"
    revenue_trend_pct: float = 12.4
    profit_trend_pct: float = 8.2


# --- SKU Detail & AI Explanation ---
class ReturnReasonBreakdown(BaseModel):
    reason: str
    count: int
    percentage: float

class SKUTrendPoint(BaseModel):
    month: str
    revenue: float
    profit: float
    return_rate: float
    profit_margin: float

class SKUDetailResponse(BaseModel):
    metric: SKUMetricResponse
    product: Optional[ProductResponse] = None
    return_reasons: List[ReturnReasonBreakdown]
    monthly_trends: List[SKUTrendPoint]
    ai_explanation: Optional[Dict[str, Any]] = None


# --- Calculation Config ---
class CalculationConfigResponse(BaseModel):
    id: str
    organization_id: str
    settlement_is_net: bool
    deduct_marketplace_fees: bool
    include_shipping: bool
    include_return_cost: bool
    critical_risk_margin_threshold: float
    warning_risk_return_rate_threshold: float
    warning_risk_rto_rate_threshold: float
    class Config:
        from_attributes = True

class CalculationConfigUpdate(BaseModel):
    settlement_is_net: Optional[bool] = None
    deduct_marketplace_fees: Optional[bool] = None
    include_shipping: Optional[bool] = None
    include_return_cost: Optional[bool] = None
    critical_risk_margin_threshold: Optional[float] = None
    warning_risk_return_rate_threshold: Optional[float] = None
    warning_risk_rto_rate_threshold: Optional[float] = None
