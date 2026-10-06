import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models.models import User, Organization, OrganizationMember, OrderItemLedger, SKUMetric
from app.auth.auth import create_access_token

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def test_client_and_db():
    from app.database import engine as app_engine
    Base.metadata.create_all(bind=app_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=app_engine)
    db = TestingSessionLocal()

    # Scope cleanup strictly to test organization to preserve known-good development data
    db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == "test-org-reg-id").delete()
    db.query(SKUMetric).filter(SKUMetric.organization_id == "test-org-reg-id").delete()
    db.commit()

    user = db.query(User).filter(User.email == "testreg@example.com").first()
    if not user:
        user = User(id="test-user-reg-id", email="testreg@example.com", hashed_password="pw", name="Reg User")
        db.add(user)
        db.flush()

    org = db.query(Organization).filter(Organization.id == "test-org-reg-id").first()
    if not org:
        org = Organization(id="test-org-reg-id", name="Reg Test Store", owner_id=user.id)
        db.add(org)
        db.flush()

    member = db.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id, OrganizationMember.user_id == user.id).first()
    if not member:
        member = OrganizationMember(organization_id=org.id, user_id=user.id, role="owner")
        db.add(member)
    db.commit()

    client = TestClient(app)

    token = create_access_token(data={"sub": user.id})
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": org.id
    }

    yield client, db, headers, org.id

    db.close()

def test_real_flipkart_upload_and_metrics_regression(test_client_and_db):
    client, db, headers, org_id = test_client_and_db

    from pathlib import Path
    tests_dir = Path(__file__).resolve().parent
    file_path = str(tests_dir / "fixtures" / "sample_flipkart.xlsx")
    assert os.path.exists(file_path), f"Sanitized Flipkart test fixture missing at {file_path}"

    # 1. Step 1: Upload File
    with open(file_path, "rb") as f:
        resp_upload = client.post(
            "/api/v1/upload/file",
            files={"file": ("flipkart_sales.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"marketplace": "Flipkart"},
            headers=headers
        )

    assert resp_upload.status_code == 200
    upload_res = resp_upload.json()
    upload_id = upload_res["upload_id"]
    assert upload_id is not None

    # 2. Step 2: Process Mapping
    resp_process = client.post(
        "/api/v1/upload/process-mapping",
        json={
            "upload_id": upload_id,
            "marketplace": "Flipkart",
            "mapping": upload_res.get("auto_mapping", {}),
            "deduplication_mode": "replace"
        },
        headers=headers
    )
    assert resp_process.status_code == 200
    proc_res = resp_process.json()
    assert proc_res["sales_records_count"] == 2373

    # 3. Direct DB Ledger Assertions
    ledger_items = db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == org_id).all()
    assert len(ledger_items) == 2373

    sale_events = [i for i in ledger_items if i.event_subtype == "SALE"]
    return_events = [i for i in ledger_items if i.event_subtype == "RETURN"]
    cancellation_events = [i for i in ledger_items if i.event_subtype == "CANCELLATION"]
    return_cancel_events = [i for i in ledger_items if i.event_subtype == "RETURN_CANCELLATION"]

    assert len(sale_events) == 1734
    assert len(return_events) == 486
    assert len(cancellation_events) == 134
    assert len(return_cancel_events) == 19

    unique_orders = len(set(i.order_id for i in ledger_items))
    unique_order_items = len(set(i.order_item_id for i in ledger_items))
    unique_skus = len(set(i.sku for i in ledger_items if i.sku))

    assert unique_orders == 1752
    assert unique_order_items == 1766
    assert unique_skus == 57

    sale_items = set(i.order_item_id for i in sale_events)
    return_items = set(i.order_item_id for i in return_events)
    sale_and_return_items = len(sale_items.intersection(return_items))

    assert len(sale_items) == 1698
    assert len(return_items) == 477
    assert sale_and_return_items == 411

    sale_linked_rate = round((411 / 1698 * 100), 1)
    assert sale_linked_rate == 24.2

    # 4. Dashboard Overview API Endpoint
    resp_overview = client.get("/api/v1/dashboard/overview", headers=headers)
    assert resp_overview.status_code == 200
    ov = resp_overview.json()

    assert ov["sales_value"] == 319328.0
    assert ov["returned_value"] == 97967.0
    assert ov["sale_events_count"] == 1734
    assert ov["return_events_count"] == 486
    assert ov["cancellation_events_count"] == 134
    assert ov["unique_orders_count"] == 1752
    assert ov["unique_skus_count"] == 57
    assert ov["sale_linked_return_rate"] == 24.2

    # 5. Products Needing Attention Endpoint
    resp_attention = client.get("/api/v1/dashboard/products-needing-attention", headers=headers)
    assert resp_attention.status_code == 200
    attention_items = resp_attention.json()
    assert len(attention_items) > 0

    # 6. Product Detail Endpoint for L-ORI-JHU-SL
    resp_detail = client.get("/api/v1/dashboard/products/L-ORI-JHU-SL", headers=headers)
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["sku"] == "L-ORI-JHU-SL"
