import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.models import (
    User, Organization, OrganizationMember,
    Product, OrderItemLedger, UploadedFile, SKUMetric
)
from app.auth.auth import create_access_token

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

def test_company_a_and_company_b_multi_tenant_isolation(isolated_db):
    db, client = isolated_db

    # 1. Company A: Register
    resp_a = client.post("/api/v1/auth/signup", json={
        "email": "owner_a@companya.com",
        "password": "PasswordCompanyA123!",
        "name": "Alice Owner",
        "company_name": "Company A Inc"
    })
    assert resp_a.status_code == 200
    token_a = resp_a.json()["access_token"]
    org_a_id = resp_a.json()["active_organization_id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Organization-ID": org_a_id}

    # Add Company A data directly into DB
    prod_a = Product(
        organization_id=org_a_id,
        sku="SKU-COMPANY-A",
        product_name="Product A",
        purchase_cost=100.0,
        selling_price=500.0
    )
    db.add(prod_a)

    upload_a = UploadedFile(
        id="upload-a-id",
        organization_id=org_a_id,
        filename="sales_company_a.xlsx",
        storage_path="uploads/comp_a.xlsx",
        upload_status="completed",
        rows_processed=10
    )
    db.add(upload_a)

    ledger_sale_a = OrderItemLedger(
        organization_id=org_a_id,
        upload_id=upload_a.id,
        order_id="ORD-A-001",
        order_item_id="ITEM-A-001",
        sku="SKU-COMPANY-A",
        event_subtype="SALE",
        quantity=1,
        invoice_amount=500.0
    )
    ledger_return_a = OrderItemLedger(
        organization_id=org_a_id,
        upload_id=upload_a.id,
        order_id="ORD-A-001",
        order_item_id="ITEM-A-001",
        sku="SKU-COMPANY-A",
        event_subtype="RETURN",
        quantity=1,
        invoice_amount=500.0
    )
    db.add_all([ledger_sale_a, ledger_return_a])

    metric_a = SKUMetric(
        organization_id=org_a_id,
        sku="SKU-COMPANY-A",
        revenue=500.0,
        units_sold=1,
        returned_units=1,
        return_value=500.0
    )
    db.add(metric_a)
    db.commit()

    # Company A can see its products, returns, and overview
    prods_res_a = client.get("/api/v1/products", headers=headers_a)
    assert prods_res_a.status_code == 200
    assert len(prods_res_a.json()) == 1
    assert prods_res_a.json()[0]["sku"] == "SKU-COMPANY-A"

    returns_res_a = client.get("/api/v1/dashboard/returns-summary", headers=headers_a)
    assert returns_res_a.status_code == 200
    assert returns_res_a.json()["total_return_events"] == 1

    overview_res_a = client.get("/api/v1/dashboard/overview", headers=headers_a)
    assert overview_res_a.status_code == 200

    # 2. Company B: Register
    resp_b = client.post("/api/v1/auth/signup", json={
        "email": "owner_b@companyb.com",
        "password": "PasswordCompanyB123!",
        "name": "Bob Owner",
        "company_name": "Company B LLC"
    })
    assert resp_b.status_code == 200
    token_b = resp_b.json()["access_token"]
    org_b_id = resp_b.json()["active_organization_id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Organization-ID": org_b_id}

    # Company B starts completely empty
    prods_b = client.get("/api/v1/products", headers=headers_b).json()
    assert len(prods_b) == 0

    returns_b = client.get("/api/v1/dashboard/returns-summary", headers=headers_b).json()
    assert returns_b["total_return_events"] == 0

    imports_b = client.get("/api/v1/imports", headers=headers_b).json()
    assert len(imports_b) == 0

    # 3. Cross-Tenant Attack Scenarios: Company B attempts accessing Company A resources

    # Attempt 1: B tries to pass Company A's organization ID in header -> 403 Forbidden
    spoof_headers = {"Authorization": f"Bearer {token_b}", "X-Organization-ID": org_a_id}
    resp_spoof = client.get("/api/v1/products", headers=spoof_headers)
    assert resp_spoof.status_code == 403
    assert "Access denied" in resp_spoof.json()["detail"]

    # Attempt 2: B tries to delete Company A's import -> 404 Not Found (within B's scope)
    resp_del = client.delete(f"/api/v1/imports/{upload_a.id}", headers=headers_b)
    assert resp_del.status_code == 404

    # Attempt 3: B tries to query Company A's product detail
    resp_sku_detail = client.get(f"/api/v1/dashboard/products/{prod_a.sku}", headers=headers_b)
    assert resp_sku_detail.status_code in [404, 200]
    if resp_sku_detail.status_code == 200:
        # If returns empty metric container, ensure it has 0 units and no Company A data
        assert resp_sku_detail.json().get("units_sold", 0) == 0

    # Attempt 4: B tries to update Company A's calculation configuration -> 403 Forbidden
    resp_update_conf = client.put("/api/v1/organizations/config", json={
        "critical_risk_margin_threshold": 99.0
    }, headers=spoof_headers)
    assert resp_update_conf.status_code == 403
