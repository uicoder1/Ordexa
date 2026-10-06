import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    is_platform_admin = Column(Boolean, default=False)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    memberships = relationship("OrganizationMember", back_populates="user", cascade="all, delete-orphan")


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    sales_channels = Column(Text, default="Amazon,Flipkart,Shopify")
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")
    subscription = relationship("OrganizationSubscription", back_populates="organization", uselist=False, cascade="all, delete-orphan")


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id = Column(String, primary_key=True, default=generate_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String, default="owner")
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="memberships")


class OrganizationSubscription(Base):
    __tablename__ = "organization_subscriptions"

    id = Column(String, primary_key=True, default=generate_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, unique=True, index=True)
    plan = Column(String, default="starter")
    status = Column(String, default="active")
    billing_cycle = Column(String, default="monthly")
    monthly_upload_limit = Column(Integer, default=50)
    monthly_transaction_limit = Column(Integer, default=10000)
    max_skus = Column(Integer, default=500)
    uploads_used_this_month = Column(Integer, default=0)
    transactions_used_this_month = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="subscription")


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, default=generate_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    sku = Column(String, nullable=False, index=True)
    product_name = Column(String, nullable=False)
    category = Column(String, default="General")
    purchase_cost = Column(Float, default=0.0)
    selling_price = Column(Float, default=0.0)
    marketplace = Column(String, default="All")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_org_sku_unique", "organization_id", "sku", unique=True),
    )


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, default=generate_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    upload_id = Column(String, ForeignKey("uploaded_files.id"), nullable=True, index=True)
    order_id = Column(String, nullable=False, index=True)
    transaction_id = Column(String, nullable=True, index=True)
    sku = Column(String, nullable=False, index=True)
    product_name = Column(String, nullable=True)
    order_date = Column(DateTime, default=datetime.utcnow, index=True)
    quantity = Column(Integer, default=1)
    selling_price = Column(Float, default=0.0)
    order_status = Column(String, default="Delivered") # Delivered, Cancelled, Returned, RTO
    marketplace = Column(String, default="Amazon")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_org_order_sku_unique", "organization_id", "order_id", "sku", unique=True),
        Index("idx_org_order_date", "organization_id", "order_date"),
    )


class Return(Base):
    __tablename__ = "returns"

    id = Column(String, primary_key=True, default=generate_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    upload_id = Column(String, ForeignKey("uploaded_files.id"), nullable=True, index=True)
    order_id = Column(String, nullable=False, index=True)
    sku = Column(String, nullable=False, index=True)
    return_date = Column(DateTime, default=datetime.utcnow)
    quantity = Column(Integer, default=1)
    return_reason = Column(String, default="Customer Choice")
    return_cost = Column(Float, default=0.0)
    refund_amount = Column(Float, default=0.0)
    is_rto = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_org_return_order_sku", "organization_id", "order_id", "sku", unique=False),
    )


class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(String, primary_key=True, default=generate_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    upload_id = Column(String, ForeignKey("uploaded_files.id"), nullable=True, index=True)
    transaction_id = Column(String, nullable=True, index=True)
    order_id = Column(String, nullable=False, index=True)
    sku = Column(String, nullable=False, index=True)
    settlement_amount = Column(Float, default=0.0)
    marketplace_fee = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    shipping_charge = Column(Float, default=0.0)
    return_charge = Column(Float, default=0.0)
    other_charge = Column(Float, default=0.0)
    settlement_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_org_settlement_txn_sku", "organization_id", "transaction_id", "sku", unique=False),
    )


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(String, primary_key=True, default=generate_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    marketplace = Column(String, default="Generic")
    storage_path = Column(String, nullable=False)
    file_type = Column(String, default="csv")
    file_size = Column(Integer, default=0)
    upload_status = Column(String, default="uploaded")
    rows_processed = Column(Integer, default=0)
    rows_failed = Column(Integer, default=0)
    column_mapping = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


class SKUMetric(Base):
    __tablename__ = "sku_metrics"

    id = Column(String, primary_key=True, default=generate_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    sku = Column(String, nullable=False, index=True)
    period_name = Column(String, default="All Time")
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    total_orders = Column(Integer, default=0)
    units_sold = Column(Integer, default=0)
    returned_units = Column(Integer, default=0)
    cancellation_units = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)
    returns_count = Column(Integer, default=0)
    return_rate = Column(Float, default=0.0)
    sale_linked_return_rate = Column(Float, default=0.0)
    rto_count = Column(Integer, default=0)
    rto_rate = Column(Float, nullable=True)
    total_product_cost = Column(Float, nullable=True)
    marketplace_fees = Column(Float, nullable=True)
    shipping_cost = Column(Float, default=0.0)
    return_cost = Column(Float, default=0.0)
    return_value = Column(Float, default=0.0)
    refund_amount = Column(Float, default=0.0)
    net_settlement = Column(Float, nullable=True)
    actual_profit = Column(Float, nullable=True)
    profit_margin = Column(Float, nullable=True)
    profit_leakage = Column(Float, nullable=True)
    cogs_available = Column(Boolean, default=False)
    settlement_available = Column(Boolean, default=False)
    rto_available = Column(Boolean, default=False)
    data_confidence = Column(String, default="INSUFFICIENT")
    risk_level = Column(String, default="HEALTHY")
    recommended_action = Column(String, default="Healthy")
    reason = Column(String, nullable=True)
    calculated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_org_sku_metric_unique", "organization_id", "sku", unique=True),
    )


class CalculationConfig(Base):
    __tablename__ = "calculation_configs"

    id = Column(String, primary_key=True, default=generate_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, unique=True, index=True)
    settlement_is_net = Column(Boolean, default=True)
    deduct_marketplace_fees = Column(Boolean, default=False)
    include_shipping = Column(Boolean, default=True)
    include_return_cost = Column(Boolean, default=True)
    critical_risk_margin_threshold = Column(Float, default=5.0)
    warning_risk_return_rate_threshold = Column(Float, default=15.0)
    warning_risk_rto_rate_threshold = Column(Float, default=10.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrderItemLedger(Base):
    __tablename__ = "order_item_ledger"

    id = Column(String, primary_key=True, default=generate_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    upload_id = Column(String, ForeignKey("uploaded_files.id"), nullable=True, index=True)

    seller_gstin = Column(String, nullable=True)
    order_id = Column(String, nullable=False, index=True)
    order_item_id = Column(String, nullable=False, index=True)
    product_name = Column(String, nullable=True)
    fsn = Column(String, nullable=True)
    sku = Column(String, nullable=False, index=True)
    hsn_code = Column(String, nullable=True)
    event_type = Column(String, nullable=True)
    event_subtype = Column(String, nullable=False, index=True)  # SALE, RETURN, CANCELLATION, RETURN_CANCELLATION
    order_type = Column(String, nullable=True)                  # PREPAID, COD, etc.
    fulfilment_type = Column(String, nullable=True)              # NON_FBF, FBF, etc.
    order_date = Column(DateTime, nullable=True, index=True)
    order_approval_date = Column(DateTime, nullable=True)
    quantity = Column(Integer, default=1)
    shipped_from_state = Column(String, nullable=True)
    warehouse_id = Column(String, nullable=True)

    price_before_discount = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    seller_share = Column(Float, default=0.0)
    bank_offer_share = Column(Float, default=0.0)
    price_after_discount = Column(Float, default=0.0)
    shipping_charge = Column(Float, default=0.0)
    invoice_amount = Column(Float, default=0.0)
    taxable_value = Column(Float, default=0.0)

    igst_rate = Column(Float, default=0.0)
    igst_amount = Column(Float, default=0.0)
    cgst_rate = Column(Float, default=0.0)
    cgst_amount = Column(Float, default=0.0)
    sgst_rate = Column(Float, default=0.0)
    sgst_amount = Column(Float, default=0.0)

    tcs = Column(Float, default=0.0)
    tds = Column(Float, default=0.0)

    buyer_invoice_id = Column(String, nullable=True)
    buyer_invoice_date = Column(DateTime, nullable=True)
    buyer_invoice_amount = Column(Float, default=0.0)

    customer_billing_pincode = Column(String, nullable=True)
    customer_billing_state = Column(String, nullable=True)
    customer_delivery_pincode = Column(String, nullable=True)
    customer_delivery_state = Column(String, nullable=True)

    usual_price = Column(Float, default=0.0)
    is_shopsy = Column(Boolean, default=False)
    marketplace = Column(String, default="Flipkart")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_ledger_org_order_item_evt", "organization_id", "order_id", "order_item_id", "event_subtype"),
    )


class CashBackLedger(Base):
    __tablename__ = "cashback_ledger"

    id = Column(String, primary_key=True, default=generate_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False, index=True)
    upload_id = Column(String, ForeignKey("uploaded_files.id"), nullable=True, index=True)

    seller_gstin = Column(String, nullable=True)
    order_id = Column(String, nullable=False, index=True)
    order_item_id = Column(String, nullable=False, index=True)
    document_type = Column(String, nullable=True)
    document_subtype = Column(String, nullable=True)
    credit_debit_note_id = Column(String, nullable=True)
    invoice_amount = Column(Float, default=0.0)
    invoice_date = Column(DateTime, nullable=True)
    taxable_value = Column(Float, default=0.0)

    igst_amount = Column(Float, default=0.0)
    cgst_amount = Column(Float, default=0.0)
    sgst_amount = Column(Float, default=0.0)

    tcs = Column(Float, default=0.0)
    tds = Column(Float, default=0.0)
    customer_delivery_state = Column(String, nullable=True)
    is_shopsy = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_cb_org_order_item", "organization_id", "order_id", "order_item_id"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_audit_org_action", "organization_id", "action"),
        Index("idx_audit_created_at", "created_at"),
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_reset_token_user_expires", "user_id", "expires_at"),
    )
