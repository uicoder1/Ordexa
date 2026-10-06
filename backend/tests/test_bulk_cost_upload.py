import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.models import (
    User, Organization, OrganizationMember,
    Product, OrderItemLedger, SKUMetric
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

def test_bulk_cost_upload_persistence_and_metrics_recalculation(isolated_db):
    db, client = isolated_db

    # Setup tenant
    user = User(id="user-cost-test", email="cost_tester@ordexa.com", hashed_password="pw", name="Tester")
    db.add(user)
    org = Organization(id="org-cost-test", name="Cost Test Org", owner_id=user.id)
    db.add(org)
    mem = OrganizationMember(organization_id=org.id, user_id=user.id, role="owner")
    db.add(mem)

    # Add ledger sales for SKU-ABC and SKU-XYZ
    db.add(OrderItemLedger(
        organization_id=org.id,
        order_id="ORD-1",
        order_item_id="ITEM-1",
        sku="SKU-ABC",
        event_subtype="SALE",
        quantity=5,
        invoice_amount=2500.0
    ))
    db.add(OrderItemLedger(
        organization_id=org.id,
        order_id="ORD-2",
        order_item_id="ITEM-2",
        sku="SKU-XYZ",
        event_subtype="SALE",
        quantity=2,
        invoice_amount=1200.0
    ))
    db.commit()

    token = create_access_token(data={"sub": user.id})
    headers = {"Authorization": f"Bearer {token}", "X-Organization-ID": org.id}

    # CSV with new purchase costs
    csv_content = (
        "SKU,Purchase Cost\n"
        "SKU-ABC,250.00\n"
        "SKU-XYZ,300.00\n"
    )

    file_bytes = io.BytesIO(csv_content.encode("utf-8"))
    response = client.post(
        "/api/v1/products/bulk-cost-upload",
        files={"file": ("costs.csv", file_bytes, "text/csv")},
        headers=headers
    )

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["total_processed"] == 2
    assert "recalculated successfully" in res_data["message"]

    # 1. Verify Database Persistence in Product Table
    prod_abc = db.query(Product).filter(Product.organization_id == org.id, Product.sku == "SKU-ABC").first()
    assert prod_abc is not None
    assert prod_abc.purchase_cost == 250.00

    prod_xyz = db.query(Product).filter(Product.organization_id == org.id, Product.sku == "SKU-XYZ").first()
    assert prod_xyz is not None
    assert prod_xyz.purchase_cost == 300.00

    # 2. Verify Refreshed Financial / SKU Metrics
    metric_abc = db.query(SKUMetric).filter(SKUMetric.organization_id == org.id, SKUMetric.sku == "SKU-ABC").first()
    assert metric_abc is not None
    assert metric_abc.cogs_available is True
    # 1 unique sale item * 250 = 250 total product cost
    assert metric_abc.total_product_cost == 250.00

    metric_xyz = db.query(SKUMetric).filter(SKUMetric.organization_id == org.id, SKUMetric.sku == "SKU-XYZ").first()
    assert metric_xyz is not None
    assert metric_xyz.cogs_available is True
    # 1 unique sale item * 300 = 300 total product cost
    assert metric_xyz.total_product_cost == 300.00
