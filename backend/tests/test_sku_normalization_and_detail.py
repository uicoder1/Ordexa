import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.models import Organization, OrderItemLedger, Product, SKUMetric, User, OrganizationMember
from app.services.flipkart_parser import normalize_sku, normalize_product_name

def test_normalize_product_name_with_quotes():
    raw1 = '"""Bhumi09 Bhumi09 Pack of 2 Traditional Wedding New Stylish Gold Mangalsutra for Women Brass Mangalsutra"""'
    exp1 = 'Bhumi09 Pack of 2 Traditional Wedding New Stylish Gold Mangalsutra for Women Brass Mangalsutra'
    assert normalize_product_name(raw1) == exp1

    raw2 = '"""BRANDSOON 18 Inch Tanmnaiya for Women and Girls Mangalsutra Gold-plated Plated Brass Chain"""'
    exp2 = 'BRANDSOON 18 Inch Tanmnaiya for Women and Girls Mangalsutra Gold-plated Plated Brass Chain'
    assert normalize_product_name(raw2) == exp2

def test_normalize_product_name_duplicate_leading_brand():
    raw = '"""Bhumi09 Bhumi09 1 Gram Gold fancy Mangalsura For Women 18 inch Alloy Mangalsutra"""'
    exp = 'Bhumi09 1 Gram Gold fancy Mangalsura For Women 18 inch Alloy Mangalsutra'
    assert normalize_product_name(raw) == exp

def test_normalize_product_name_preserves_legitimate_words():
    raw = 'Gold Pack of 2 Gold Ring for Women'
    assert normalize_product_name(raw) == 'Gold Pack of 2 Gold Ring for Women'
from app.services.calculation_engine import calculation_engine
from app.auth.auth import create_access_token

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base

from sqlalchemy.pool import StaticPool

@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def test_user(db_session):
    u = User(email="test_sku_normalizer@example.com", hashed_password="pw", name="Tester")
    db_session.add(u)
    db_session.commit()
    return u

@pytest.fixture
def org(db_session, test_user):
    o = Organization(name="SKU Test Org", owner_id=test_user.id)
    db_session.add(o)
    db_session.commit()
    m = OrganizationMember(organization_id=o.id, user_id=test_user.id, role="owner")
    db_session.add(m)
    db_session.commit()
    return o

from app.database import get_db

@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()

@pytest.fixture
def tenant_headers(test_user, org):
    token = create_access_token({"sub": test_user.id})
    return {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": org.id
    }

def test_normalize_sku_with_quotes():
    assert normalize_sku('"""SKU:L-ORI-JHU-SL"""') == "L-ORI-JHU-SL"
    assert normalize_sku('"""SKU:L-ORI-Mangalsutra"""') == "L-ORI-Mangalsutra"
    assert normalize_sku('"L-ORI-JHU-SL"') == "L-ORI-JHU-SL"
    assert normalize_sku("'L-ORI-JHU-SL'") == "L-ORI-JHU-SL"

def test_normalize_sku_with_sku_prefix():
    assert normalize_sku('SKU:L-ORI-JHU-SL') == "L-ORI-JHU-SL"
    assert normalize_sku('sku:L-ORI-Mangalsutra') == "L-ORI-Mangalsutra"
    assert normalize_sku('Sku: OR-EAR-A-3') == "OR-EAR-A-3"

def test_product_detail_existing_sku(db_session, client, tenant_headers, org):
    db_session.add(OrderItemLedger(
        organization_id=org.id,
        order_id="ORD-1",
        order_item_id="ITEM-1",
        sku='"""SKU:L-ORI-JHU-SL"""',
        event_subtype="SALE",
        invoice_amount=500.0
    ))
    db_session.commit()
    
    res = client.get("/api/v1/dashboard/products/detail?sku=L-ORI-JHU-SL", headers=tenant_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["sku"] == "L-ORI-JHU-SL"
    assert data["top_summary"]["sale_items"] == 1

def test_product_detail_unknown_sku(client, tenant_headers):
    res = client.get("/api/v1/dashboard/products/detail?sku=UNKNOWN-NONEXISTENT-SKU", headers=tenant_headers)
    assert res.status_code == 404
    assert "Product not found" in res.json()["detail"]

def test_product_list_sku_matches_detail_sku(db_session, client, tenant_headers, org):
    db_session.add(OrderItemLedger(
        organization_id=org.id,
        order_id="ORD-TEST",
        order_item_id="ITEM-TEST",
        sku='"""SKU:OR-BRA-A-1"""',
        event_subtype="SALE",
        invoice_amount=300.0
    ))
    db_session.commit()
    calculation_engine.calculate_sku_metrics(db_session, org.id)

    skus_res = client.get("/api/v1/dashboard/skus", headers=tenant_headers)
    assert skus_res.status_code == 200
    skus = skus_res.json()
    assert len(skus) > 0

    for item in skus:
        sku = item["sku"]
        detail_res = client.get(f"/api/v1/dashboard/products/detail?sku={sku}", headers=tenant_headers)
        assert detail_res.status_code == 200, f"Detail for SKU {sku} returned {detail_res.status_code}"

def test_unique_sale_items(db_session, org):
    db_session.add(OrderItemLedger(
        organization_id=org.id, order_id="O1", order_item_id="ITM1", sku="L-ORI-JHU-SL", event_subtype="SALE", invoice_amount=100.0
    ))
    db_session.add(OrderItemLedger(
        organization_id=org.id, order_id="O1", order_item_id="ITM1", sku="L-ORI-JHU-SL", event_subtype="SALE", invoice_amount=50.0
    ))
    db_session.add(OrderItemLedger(
        organization_id=org.id, order_id="O2", order_item_id="ITM2", sku="L-ORI-JHU-SL", event_subtype="SALE", invoice_amount=150.0
    ))
    db_session.commit()

    calculation_engine.calculate_sku_metrics(db_session, org.id)
    metric = db_session.query(SKUMetric).filter(SKUMetric.organization_id == org.id, SKUMetric.sku == "L-ORI-JHU-SL").first()
    assert metric.units_sold == 2

def test_unique_return_items(db_session, org):
    db_session.add(OrderItemLedger(
        organization_id=org.id, order_id="O1", order_item_id="ITM1", sku="L-ORI-JHU-SL", event_subtype="RETURN", invoice_amount=100.0
    ))
    db_session.add(OrderItemLedger(
        organization_id=org.id, order_id="O1", order_item_id="ITM1", sku="L-ORI-JHU-SL", event_subtype="RETURN", invoice_amount=50.0
    ))
    db_session.commit()

    calculation_engine.calculate_sku_metrics(db_session, org.id)
    metric = db_session.query(SKUMetric).filter(SKUMetric.organization_id == org.id, SKUMetric.sku == "L-ORI-JHU-SL").first()
    assert metric.returned_units == 1

def test_sale_and_return_items(db_session, org):
    db_session.add(OrderItemLedger(organization_id=org.id, order_id="O1", order_item_id="ITM1", sku="L-ORI-JHU-SL", event_subtype="SALE", invoice_amount=100.0))
    db_session.add(OrderItemLedger(organization_id=org.id, order_id="O1", order_item_id="ITM1", sku="L-ORI-JHU-SL", event_subtype="RETURN", invoice_amount=100.0))
    db_session.add(OrderItemLedger(organization_id=org.id, order_id="O2", order_item_id="ITM2", sku="L-ORI-JHU-SL", event_subtype="SALE", invoice_amount=100.0))
    db_session.commit()

    calculation_engine.calculate_sku_metrics(db_session, org.id)
    detail = calculation_engine.get_sku_detail(db_session, org.id, "L-ORI-JHU-SL")
    assert detail["top_summary"]["sale_items"] == 2
    assert detail["top_summary"]["returned_items"] == 1
    assert detail["top_summary"]["sale_linked_return_rate"] == 50.0

def test_sale_linked_return_rate(db_session, org):
    for i in range(1, 4):
        db_session.add(OrderItemLedger(organization_id=org.id, order_id=f"O{i}", order_item_id=f"ITM{i}", sku="L-ORI-JHU-SL", event_subtype="SALE", invoice_amount=100.0))
    db_session.add(OrderItemLedger(organization_id=org.id, order_id="O1", order_item_id="ITM1", sku="L-ORI-JHU-SL", event_subtype="RETURN", invoice_amount=100.0))
    db_session.commit()

    calculation_engine.calculate_sku_metrics(db_session, org.id)
    detail = calculation_engine.get_sku_detail(db_session, org.id, "L-ORI-JHU-SL")
    assert detail["top_summary"]["sale_linked_return_rate"] == 33.33
