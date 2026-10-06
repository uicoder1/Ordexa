import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.models import (
    User, Organization, OrganizationMember,
    Product, OrderItemLedger, CashBackLedger, UploadedFile, SKUMetric, Order, Return, Settlement, AuditLog
)
from app.auth.auth import create_access_token
from app.services.calculation_engine import calculation_engine

@pytest.fixture
def isolated_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield db, TestClient(app)
    app.dependency_overrides.clear()
    db.close()

def test_transactional_import_deletion(isolated_db):
    db, client = isolated_db

    # Create owner user and organization
    user = User(id="u-del-owner", email="del_owner@ordexa.com", hashed_password="pw", name="Owner")
    db.add(user)
    org = Organization(id="org-del-test", name="Deletion Test Org", owner_id=user.id)
    db.add(org)
    mem = OrganizationMember(organization_id=org.id, user_id=user.id, role="owner")
    db.add(mem)

    # 1. Create a temporary test import with its ledger rows
    upload = UploadedFile(
        id="test-upload-to-delete",
        organization_id=org.id,
        filename="temp_test_report.xlsx",
        marketplace="Flipkart",
        storage_path="uploads/temp_test.xlsx",
        upload_status="completed",
        rows_processed=4
    )
    db.add(upload)

    # 2. Add associated OrderItemLedger rows
    db.add(OrderItemLedger(
        organization_id=org.id,
        upload_id=upload.id,
        order_id="ORD-DEL-1",
        order_item_id="ITEM-DEL-1",
        sku="SKU-DEL",
        event_subtype="SALE",
        quantity=1,
        invoice_amount=500.0
    ))
    db.add(OrderItemLedger(
        organization_id=org.id,
        upload_id=upload.id,
        order_id="ORD-DEL-1",
        order_item_id="ITEM-DEL-1",
        sku="SKU-DEL",
        event_subtype="RETURN",
        quantity=1,
        invoice_amount=500.0
    ))

    # 3. Add associated CashBackLedger row
    db.add(CashBackLedger(
        organization_id=org.id,
        upload_id=upload.id,
        order_id="ORD-DEL-1",
        order_item_id="ITEM-DEL-1",
        invoice_amount=50.0
    ))

    # 4. Add associated legacy rows
    db.add(Order(organization_id=org.id, upload_id=upload.id, order_id="ORD-DEL-1", sku="SKU-DEL"))
    db.add(Return(organization_id=org.id, upload_id=upload.id, order_id="ORD-DEL-1", sku="SKU-DEL"))
    db.add(Settlement(organization_id=org.id, upload_id=upload.id, order_id="ORD-DEL-1", sku="SKU-DEL"))

    db.commit()

    # Pre-calculate SKU metrics
    calculation_engine.calculate_sku_metrics(db, org.id)
    metric_before = db.query(SKUMetric).filter(SKUMetric.organization_id == org.id, SKUMetric.sku == "SKU-DEL").first()
    assert metric_before is not None
    assert metric_before.units_sold == 1
    assert metric_before.returned_units == 1

    token = create_access_token(data={"sub": user.id})
    headers = {"Authorization": f"Bearer {token}", "X-Organization-ID": org.id}

    # Execute DELETE endpoint
    del_resp = client.delete(f"/api/v1/imports/{upload.id}", headers=headers)
    assert del_resp.status_code == 200
    res_data = del_resp.json()
    assert res_data["deleted_order_items"] == 2
    assert res_data["deleted_cashback_items"] == 1

    # Verify that UploadedFile record is gone
    assert db.query(UploadedFile).filter(UploadedFile.id == upload.id).first() is None

    # Verify OrderItemLedger records are completely removed
    assert db.query(OrderItemLedger).filter(OrderItemLedger.upload_id == upload.id).count() == 0

    # Verify CashBackLedger records are completely removed
    assert db.query(CashBackLedger).filter(CashBackLedger.upload_id == upload.id).count() == 0

    # Verify legacy rows are removed
    assert db.query(Order).filter(Order.upload_id == upload.id).count() == 0
    assert db.query(Return).filter(Return.upload_id == upload.id).count() == 0
    assert db.query(Settlement).filter(Settlement.upload_id == upload.id).count() == 0

    # Verify SKU metrics were automatically recalculated to 0
    metric_after = db.query(SKUMetric).filter(SKUMetric.organization_id == org.id, SKUMetric.sku == "SKU-DEL").first()
    if metric_after:
        assert metric_after.units_sold == 0
        assert metric_after.returned_units == 0

    # Verify audit log was recorded
    audit = db.query(AuditLog).filter(AuditLog.action == "REPORT_DELETED").first()
    assert audit is not None
    assert audit.resource_id == upload.id
