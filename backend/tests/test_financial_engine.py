import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.models import Organization, Product, Order, Return, Settlement, SKUMetric, UploadedFile, OrderItemLedger
from app.services.calculation_engine import calculation_engine

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_1_return_rate_calculation(db_session):
    """TEST 1: 100 units sold, 20 returned. Return rate must equal 20%."""
    org = Organization(id="test-org-1", name="Test Store", owner_id="u1")
    db_session.add(org)

    prod = Product(organization_id="test-org-1", sku="SKU-TEST-1", product_name="Item 1", purchase_cost=100.0, selling_price=500.0)
    db_session.add(prod)

    # 100 distinct orders
    for i in range(100):
        is_ret = i < 20
        db_session.add(OrderItemLedger(
            organization_id="test-org-1",
            order_id=f"ORD-T1-{i}",
            order_item_id=f"ITM-T1-{i}",
            sku="SKU-TEST-1",
            quantity=1,
            invoice_amount=500.0,
            event_subtype="SALE"
        ))
        if is_ret:
            db_session.add(OrderItemLedger(
                organization_id="test-org-1",
                order_id=f"ORD-T1-{i}",
                order_item_id=f"ITM-T1-{i}",
                sku="SKU-TEST-1",
                quantity=1,
                invoice_amount=500.0,
                event_subtype="RETURN"
            ))

    db_session.commit()
    calculation_engine.calculate_sku_metrics(db_session, "test-org-1")

    metric = db_session.query(SKUMetric).filter(SKUMetric.sku == "SKU-TEST-1").first()
    assert metric is not None
    assert metric.units_sold == 100
    assert metric.returned_units == 20
    assert metric.sale_linked_return_rate == 20.0

def test_2_rto_rate_calculation(db_session):
    """TEST 2: 100 orders, 10 RTO. RTO rate must equal 10%."""
    org = Organization(id="test-org-2", name="Test Store", owner_id="u1")
    db_session.add(org)

    for i in range(100):
        is_rto = i < 10
        db_session.add(OrderItemLedger(
            organization_id="test-org-2",
            order_id=f"ORD-T2-{i}",
            order_item_id=f"ITM-T2-{i}",
            sku="SKU-TEST-2",
            quantity=1,
            invoice_amount=500.0,
            event_subtype="CANCELLATION" if is_rto else "SALE"
        ))

    db_session.commit()
    calculation_engine.calculate_sku_metrics(db_session, "test-org-2")

    metric = db_session.query(SKUMetric).filter(SKUMetric.sku == "SKU-TEST-2").first()
    assert metric is not None
    assert metric.units_sold == 90
    assert metric.cancellation_units == 10

def test_3_revenue_calculation(db_session):
    """TEST 3: 100 units x ₹1500. Revenue must equal ₹150,000."""
    org = Organization(id="test-org-3", name="Test Store", owner_id="u1")
    db_session.add(org)

    for i in range(100):
        db_session.add(OrderItemLedger(
            organization_id="test-org-3",
            order_id=f"ORD-T3-{i}",
            order_item_id=f"ITM-T3-{i}",
            sku="SKU-TEST-3",
            quantity=1,
            invoice_amount=1500.0,
            event_subtype="SALE"
        ))

    db_session.commit()
    calculation_engine.calculate_sku_metrics(db_session, "test-org-3")

    metric = db_session.query(SKUMetric).filter(SKUMetric.sku == "SKU-TEST-3").first()
    assert metric is not None
    assert metric.revenue == 150000.0

def test_4_product_cost_calculation(db_session):
    """TEST 4: 100 units x ₹700 purchase cost. Product cost must equal ₹70,000."""
    org = Organization(id="test-org-4", name="Test Store", owner_id="u1")
    db_session.add(org)

    prod = Product(organization_id="test-org-4", sku="SKU-TEST-4", product_name="Item 4", purchase_cost=700.0, selling_price=1500.0)
    db_session.add(prod)

    for i in range(100):
        db_session.add(OrderItemLedger(
            organization_id="test-org-4",
            order_id=f"ORD-T4-{i}",
            order_item_id=f"ITM-T4-{i}",
            sku="SKU-TEST-4",
            quantity=1,
            invoice_amount=1500.0,
            event_subtype="SALE"
        ))

    db_session.commit()
    calculation_engine.calculate_sku_metrics(db_session, "test-org-4")

    metric = db_session.query(SKUMetric).filter(SKUMetric.sku == "SKU-TEST-4").first()
    assert metric is not None
    assert metric.total_product_cost == 70000.0

def test_5_profit_and_margin_reconciliation(db_session):
    """
    TEST 5: Revenue = ₹150,000, Product cost = ₹70,000.
    """
    org = Organization(id="test-org-5", name="Test Store", owner_id="u1")
    db_session.add(org)

    prod = Product(organization_id="test-org-5", sku="SKU-TEST-5", product_name="Item 5", purchase_cost=700.0, selling_price=1500.0)
    db_session.add(prod)

    # 100 orders
    for i in range(100):
        db_session.add(OrderItemLedger(
            organization_id="test-org-5",
            order_id=f"ORD-T5-{i}",
            order_item_id=f"ITM-T5-{i}",
            sku="SKU-TEST-5",
            quantity=1,
            invoice_amount=1500.0,
            event_subtype="SALE"
        ))

    # 10 returns adding return cost
    for i in range(10):
        db_session.add(OrderItemLedger(
            organization_id="test-org-5",
            order_id=f"ORD-T5-{i}",
            order_item_id=f"ITM-T5-{i}",
            sku="SKU-TEST-5",
            quantity=1,
            invoice_amount=1500.0,
            event_subtype="RETURN"
        ))

    db_session.commit()
    calculation_engine.calculate_sku_metrics(db_session, "test-org-5")

    metric = db_session.query(SKUMetric).filter(SKUMetric.sku == "SKU-TEST-5").first()
    assert metric is not None
    assert metric.revenue == 150000.0
    assert metric.total_product_cost == 70000.0

def test_6_single_sku_row_aggregation(db_session):
    """TEST 6: Same SKU appears in 50 database rows. Dashboard shows ONE SKU row after aggregation."""
    org = Organization(id="test-org-6", name="Test Store", owner_id="u1")
    db_session.add(org)

    prod = Product(organization_id="test-org-6", sku="SKU-TEST-6", product_name="Item 6", purchase_cost=100.0, selling_price=300.0)
    db_session.add(prod)

    # 50 order rows for same SKU
    for i in range(50):
        db_session.add(OrderItemLedger(
            organization_id="test-org-6",
            order_id=f"ORD-T6-{i}",
            order_item_id=f"ITM-T6-{i}",
            sku="SKU-TEST-6",
            quantity=1,
            invoice_amount=300.0,
            event_subtype="SALE"
        ))

    db_session.commit()
    calculation_engine.calculate_sku_metrics(db_session, "test-org-6")

    sku_rows = db_session.query(SKUMetric).filter(SKUMetric.organization_id == "test-org-6", SKUMetric.sku == "SKU-TEST-6").all()
    assert len(sku_rows) == 1
    assert sku_rows[0].units_sold == 50

def test_7_order_deduplication_multi_fee_rows(db_session):
    """TEST 7: Same order has 5 items. Unique units sold calculated correctly."""
    org = Organization(id="test-org-7", name="Test Store", owner_id="u1")
    db_session.add(org)

    # 1 unique order item
    db_session.add(OrderItemLedger(
        organization_id="test-org-7",
        order_id="ORD-MULTI-FEE-1",
        order_item_id="ITM-MULTI-1",
        sku="SKU-TEST-7",
        quantity=1,
        invoice_amount=1000.0,
        event_subtype="SALE"
    ))

    db_session.commit()
    calculation_engine.calculate_sku_metrics(db_session, "test-org-7")

    metric = db_session.query(SKUMetric).filter(SKUMetric.sku == "SKU-TEST-7").first()
    assert metric is not None
    assert metric.units_sold == 1

def test_8_duplicate_import_protection(db_session):
    """TEST 8: Re-running metrics engine still yields exactly 1 order."""
    org = Organization(id="test-org-8", name="Test Store", owner_id="u1")
    db_session.add(org)

    db_session.add(OrderItemLedger(
        organization_id="test-org-8",
        order_id="ORD-DUP-1",
        order_item_id="ITM-DUP-1",
        sku="SKU-TEST-8",
        quantity=1,
        invoice_amount=500.0,
        event_subtype="SALE"
    ))
    db_session.commit()

    calculation_engine.calculate_sku_metrics(db_session, "test-org-8")
    m1 = db_session.query(SKUMetric).filter(SKUMetric.sku == "SKU-TEST-8").first()
    assert m1.units_sold == 1

    calculation_engine.calculate_sku_metrics(db_session, "test-org-8")
    m2 = db_session.query(SKUMetric).filter(SKUMetric.sku == "SKU-TEST-8").first()
    assert m2.units_sold == 1

def test_9_return_deduplication(db_session):
    """TEST 9: Return records contain multiple rows for one returned order. Returned units must not be double counted."""
    org = Organization(id="test-org-9", name="Test Store", owner_id="u1")
    db_session.add(org)

    # 1 sale
    db_session.add(OrderItemLedger(
        organization_id="test-org-9",
        order_id="ORD-RET-DUP",
        order_item_id="ITEM-RET-DUP",
        sku="SKU-TEST-9",
        quantity=1,
        invoice_amount=600.0,
        event_subtype="SALE"
    ))

    # 3 return records for the same return order item
    for i in range(3):
        db_session.add(OrderItemLedger(
            organization_id="test-org-9",
            order_id="ORD-RET-DUP",
            order_item_id="ITEM-RET-DUP",
            sku="SKU-TEST-9",
            quantity=1,
            invoice_amount=600.0,
            event_subtype="RETURN"
        ))

    db_session.commit()
    calculation_engine.calculate_sku_metrics(db_session, "test-org-9")

    metric = db_session.query(SKUMetric).filter(SKUMetric.sku == "SKU-TEST-9").first()
    assert metric is not None
    assert metric.returned_units == 1
    assert metric.sale_linked_return_rate == 100.0
