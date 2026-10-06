import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.models import Organization, Product, OrderItemLedger, CashBackLedger, SKUMetric, Settlement
from app.services.flipkart_parser import flipkart_parser, clean_sku
from app.services.calculation_engine import calculation_engine

TEST_WORKBOOK_PATH = os.path.join(
    os.path.dirname(__file__),
    "fixtures",
    "sample_flipkart.xlsx"
)

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_1_sales_parsing():
    if not os.path.exists(TEST_WORKBOOK_PATH):
        pytest.skip("Test workbook not found at path")
    sales_recs, _ = flipkart_parser.parse_flipkart_workbook(TEST_WORKBOOK_PATH, "xlsx")
    sale_events = [r for r in sales_recs if r["event_subtype"] == "SALE"]
    assert len(sale_events) == 1734
    assert len(sales_recs) == 2373

def test_2_return_parsing():
    if not os.path.exists(TEST_WORKBOOK_PATH):
        pytest.skip("Test workbook not found at path")
    sales_recs, _ = flipkart_parser.parse_flipkart_workbook(TEST_WORKBOOK_PATH, "xlsx")
    return_events = [r for r in sales_recs if r["event_subtype"] == "RETURN"]
    assert len(return_events) == 486

def test_3_cancellation_parsing():
    if not os.path.exists(TEST_WORKBOOK_PATH):
        pytest.skip("Test workbook not found at path")
    sales_recs, _ = flipkart_parser.parse_flipkart_workbook(TEST_WORKBOOK_PATH, "xlsx")
    cancellations = [r for r in sales_recs if r["event_subtype"] == "CANCELLATION"]
    assert len(cancellations) == 134

def test_4_return_cancellation_parsing():
    if not os.path.exists(TEST_WORKBOOK_PATH):
        pytest.skip("Test workbook not found at path")
    sales_recs, _ = flipkart_parser.parse_flipkart_workbook(TEST_WORKBOOK_PATH, "xlsx")
    return_cancels = [r for r in sales_recs if r["event_subtype"] == "RETURN_CANCELLATION"]
    assert len(return_cancels) == 19

def test_5_duplicate_order_item_ids_handling(db_session):
    if not os.path.exists(TEST_WORKBOOK_PATH):
        pytest.skip("Test workbook not found at path")
    org = Organization(name="Test Org", owner_id="user1")
    db_session.add(org)
    db_session.commit()

    sales_recs, _ = flipkart_parser.parse_flipkart_workbook(TEST_WORKBOOK_PATH, "xlsx")
    for r in sales_recs:
        item = OrderItemLedger(
            organization_id=org.id,
            order_id=r["order_id"],
            order_item_id=r["order_item_id"],
            sku=r["sku"],
            event_subtype=r["event_subtype"],
            invoice_amount=r["invoice_amount"]
        )
        db_session.add(item)
    db_session.commit()

    # Total rows = 2373, unique order item ids = 1766
    unique_items_count = db_session.query(OrderItemLedger.order_item_id).filter(OrderItemLedger.organization_id == org.id).distinct().count()
    assert unique_items_count == 1766

def test_6_cash_back_report_linkage(db_session):
    if not os.path.exists(TEST_WORKBOOK_PATH):
        pytest.skip("Test workbook not found at path")
    sales_recs, cb_recs = flipkart_parser.parse_flipkart_workbook(TEST_WORKBOOK_PATH, "xlsx")
    assert len(cb_recs) == 469

    sales_items = set(r["order_item_id"] for r in sales_recs)
    cb_items = set(r["order_item_id"] for r in cb_recs)
    matching_linkage = cb_items.intersection(sales_items)
    assert len(matching_linkage) == 336

def test_7_missing_cogs_behavior(db_session):
    org = Organization(name="Test Org", owner_id="user1")
    db_session.add(org)
    db_session.commit()

    # Product without COGS (0.0)
    prod = Product(organization_id=org.id, sku="TEST-SKU-1", product_name="Test Item", purchase_cost=0.0)
    item = OrderItemLedger(organization_id=org.id, order_id="ORD1", order_item_id="ITM1", sku="TEST-SKU-1", event_subtype="SALE", invoice_amount=500.0)
    db_session.add_all([prod, item])
    db_session.commit()

    calculation_engine.calculate_sku_metrics(db_session, org.id)
    metric = db_session.query(SKUMetric).filter(SKUMetric.organization_id == org.id, SKUMetric.sku == "TEST-SKU-1").first()

    assert metric.cogs_available is False
    assert metric.total_product_cost is None
    assert metric.actual_profit is None
    assert metric.risk_level == "INSUFFICIENT_DATA"
    assert "Only 1 sale item observed" in metric.reason

def test_8_missing_settlement_behavior(db_session):
    org = Organization(name="Test Org", owner_id="user1")
    db_session.add(org)
    db_session.commit()

    prod = Product(organization_id=org.id, sku="TEST-SKU-2", product_name="Test Item 2", purchase_cost=100.0)
    item = OrderItemLedger(organization_id=org.id, order_id="ORD2", order_item_id="ITM2", sku="TEST-SKU-2", event_subtype="SALE", invoice_amount=600.0)
    db_session.add_all([prod, item])
    db_session.commit()

    calculation_engine.calculate_sku_metrics(db_session, org.id)
    metric = db_session.query(SKUMetric).filter(SKUMetric.organization_id == org.id, SKUMetric.sku == "TEST-SKU-2").first()

    assert metric.settlement_available is False
    assert metric.net_settlement is None
    assert metric.actual_profit is None

def test_9_rto_unavailable_state(db_session):
    org = Organization(name="Test Org", owner_id="user1")
    db_session.add(org)
    db_session.commit()

    item = OrderItemLedger(organization_id=org.id, order_id="ORD3", order_item_id="ITM3", sku="TEST-SKU-3", event_subtype="RETURN", invoice_amount=300.0)
    db_session.add(item)
    db_session.commit()

    calculation_engine.calculate_sku_metrics(db_session, org.id)
    metric = db_session.query(SKUMetric).filter(SKUMetric.organization_id == org.id, SKUMetric.sku == "TEST-SKU-3").first()

    assert metric.rto_available is False
    assert metric.rto_rate is None

def test_10_sku_level_sale_linked_return_calculations(db_session):
    if not os.path.exists(TEST_WORKBOOK_PATH):
        pytest.skip("Test workbook not found at path")
    org = Organization(name="Test Org", owner_id="user1")
    db_session.add(org)
    db_session.commit()

    sales_recs, _ = flipkart_parser.parse_flipkart_workbook(TEST_WORKBOOK_PATH, "xlsx")
    for r in sales_recs:
        item = OrderItemLedger(
            organization_id=org.id,
            order_id=r["order_id"],
            order_item_id=r["order_item_id"],
            sku=r["sku"],
            event_subtype=r["event_subtype"],
            invoice_amount=r["invoice_amount"]
        )
        db_session.add(item)
    db_session.commit()

    summary = calculation_engine.get_overview_summary(db_session, org.id)
    assert summary["sale_events_count"] == 1734
    assert summary["unique_sale_order_items_count"] == 1698
    assert summary["return_events_count"] == 486
    assert summary["cancellation_events_count"] == 134
    assert summary["return_cancellation_events_count"] == 19
    assert summary["sale_linked_returns_count"] == 411
    assert summary["sale_linked_return_rate"] == 24.2
    assert summary["unlinked_returns_count"] == 66

def test_11_sample_size_observation_thresholds(db_session):
    org = Organization(name="Test Org Thresholds", owner_id="user_thresh")
    db_session.add(org)
    db_session.commit()

    # Product A: 1 sale + 1 return (100% return rate) -> INSUFFICIENT DATA
    db_session.add(OrderItemLedger(organization_id=org.id, order_id="ORDA1", order_item_id="ITMA1", sku="SKU-A", event_subtype="SALE", invoice_amount=100.0))
    db_session.add(OrderItemLedger(organization_id=org.id, order_id="ORDA1", order_item_id="ITMA1", sku="SKU-A", event_subtype="RETURN", invoice_amount=100.0))

    # Product B: 2 sales + 2 returns (100% return rate) -> INSUFFICIENT DATA
    for i in range(2):
        db_session.add(OrderItemLedger(organization_id=org.id, order_id=f"ORDB{i}", order_item_id=f"ITMB{i}", sku="SKU-B", event_subtype="SALE", invoice_amount=100.0))
        db_session.add(OrderItemLedger(organization_id=org.id, order_id=f"ORDB{i}", order_item_id=f"ITMB{i}", sku="SKU-B", event_subtype="RETURN", invoice_amount=100.0))

    # Product C: 10 sales + 2 returns (20% return rate) -> WATCH (MODERATE)
    for i in range(10):
        db_session.add(OrderItemLedger(organization_id=org.id, order_id=f"ORDC{i}", order_item_id=f"ITMC{i}", sku="SKU-C", event_subtype="SALE", invoice_amount=100.0))
        if i < 2:
            db_session.add(OrderItemLedger(organization_id=org.id, order_id=f"ORDC{i}", order_item_id=f"ITMC{i}", sku="SKU-C", event_subtype="RETURN", invoice_amount=100.0))

    # Product D: 30 sales + 10 returns (33.3% return rate) -> HIGH RETURN (GOOD/NORMAL)
    for i in range(30):
        db_session.add(OrderItemLedger(organization_id=org.id, order_id=f"ORDD{i}", order_item_id=f"ITMD{i}", sku="SKU-D", event_subtype="SALE", invoice_amount=100.0))
        if i < 10:
            db_session.add(OrderItemLedger(organization_id=org.id, order_id=f"ORDD{i}", order_item_id=f"ITMD{i}", sku="SKU-D", event_subtype="RETURN", invoice_amount=100.0))

    # Product E: 55 sales + 18 returns (32.7% return rate) -> HIGH RETURN (HIGH CONFIDENCE)
    for i in range(55):
        db_session.add(OrderItemLedger(organization_id=org.id, order_id=f"ORDE{i}", order_item_id=f"ITME{i}", sku="SKU-E", event_subtype="SALE", invoice_amount=100.0))
        if i < 18:
            db_session.add(OrderItemLedger(organization_id=org.id, order_id=f"ORDE{i}", order_item_id=f"ITME{i}", sku="SKU-E", event_subtype="RETURN", invoice_amount=100.0))

    db_session.commit()

    calculation_engine.calculate_sku_metrics(db_session, org.id)

    metrics = {m.sku: m for m in db_session.query(SKUMetric).filter(SKUMetric.organization_id == org.id).all()}

    # 1 sale + 1 return -> Insufficient Data
    assert metrics["SKU-A"].risk_level == "INSUFFICIENT_DATA"
    assert metrics["SKU-A"].data_confidence == "INSUFFICIENT"
    assert "only 1 sale item observed" in metrics["SKU-A"].reason

    # 2 sales + 2 returns -> Insufficient Data
    assert metrics["SKU-B"].risk_level == "INSUFFICIENT_DATA"
    assert metrics["SKU-B"].data_confidence == "INSUFFICIENT"
    assert "only 2 sale items observed" in metrics["SKU-B"].reason

    # 10 sales = watch (MODERATE)
    assert metrics["SKU-C"].risk_level == "WATCH"
    assert metrics["SKU-C"].data_confidence == "MODERATE"

    # 30 sales = eligible for normal ranking (GOOD)
    assert metrics["SKU-D"].risk_level == "HIGH_RETURN"
    assert metrics["SKU-D"].data_confidence == "GOOD"

    # 55 sales = stronger confidence (HIGH)
    assert metrics["SKU-E"].risk_level == "HIGH_RETURN"
    assert metrics["SKU-E"].data_confidence == "HIGH"


def test_12_attention_ranking_high_volume_outranks_tiny_sample(db_session):
    from app.routers.dashboard import get_products_needing_attention

    org = Organization(name="Test Org Ranking", owner_id="user_rank")
    db_session.add(org)
    db_session.commit()

    # Product A: 2 sales, 2 returns (100% return rate)
    for i in range(2):
        db_session.add(OrderItemLedger(organization_id=org.id, order_id=f"ORDA{i}", order_item_id=f"ITMA{i}", sku="TINY-SKU", event_subtype="SALE", invoice_amount=100.0))
        db_session.add(OrderItemLedger(organization_id=org.id, order_id=f"ORDA{i}", order_item_id=f"ITMA{i}", sku="TINY-SKU", event_subtype="RETURN", invoice_amount=100.0))

    # Product B: 316 sales, 102 returns (32.3% return rate)
    for i in range(316):
        db_session.add(OrderItemLedger(organization_id=org.id, order_id=f"ORDB{i}", order_item_id=f"ITMB{i}", sku="HIGH-VOL-SKU", event_subtype="SALE", invoice_amount=100.0))
        if i < 102:
            db_session.add(OrderItemLedger(organization_id=org.id, order_id=f"ORDB{i}", order_item_id=f"ITMB{i}", sku="HIGH-VOL-SKU", event_subtype="RETURN", invoice_amount=100.0))

    db_session.commit()

    calculation_engine.calculate_sku_metrics(db_session, org.id)

    attention_list = get_products_needing_attention(limit=10, current_org=org, db=db_session)

    # High-volume product MUST outrank tiny-sample product in attention list
    skus_in_order = [p["sku"] for p in attention_list]
    assert skus_in_order[0] == "HIGH-VOL-SKU"
    assert skus_in_order[1] == "TINY-SKU"

def test_13_product_detail_9_scenarios(db_session):
    org = Organization(name="Test Org Detail Scenarios", owner_id="user_detail")
    db_session.add(org)
    db_session.commit()

    # Scenario 1, 4, 5, 6 & 9: Product with sales, returns, cancellations, return cancellations, 30+ items, multiple events per item id
    for i in range(35):
        db_session.add(OrderItemLedger(
            organization_id=org.id,
            order_id=f"ORD1_{i}",
            order_item_id=f"ITEM1_{i}",
            sku="SKU-DETAIL-1",
            event_subtype="SALE",
            invoice_amount=500.0,
            order_type="Prepaid" if i % 2 == 0 else "Postpaid",
            customer_delivery_state="Maharashtra" if i % 3 == 0 else "Karnataka"
        ))
        if i < 10:
            db_session.add(OrderItemLedger(
                organization_id=org.id,
                order_id=f"ORD1_{i}",
                order_item_id=f"ITEM1_{i}",
                sku="SKU-DETAIL-1",
                event_subtype="RETURN",
                invoice_amount=500.0,
                order_type="Prepaid" if i % 2 == 0 else "Postpaid",
                customer_delivery_state="Maharashtra" if i % 3 == 0 else "Karnataka"
            ))
        elif i < 14:
            db_session.add(OrderItemLedger(
                organization_id=org.id,
                order_id=f"ORD1_{i}",
                order_item_id=f"ITEM1_{i}",
                sku="SKU-DETAIL-1",
                event_subtype="CANCELLATION",
                invoice_amount=500.0
            ))
        elif i < 16:
            db_session.add(OrderItemLedger(
                organization_id=org.id,
                order_id=f"ORD1_{i}",
                order_item_id=f"ITEM1_{i}",
                sku="SKU-DETAIL-1",
                event_subtype="RETURN_CANCELLATION",
                invoice_amount=500.0
            ))

    # Scenario 2: Product with no returns
    for i in range(15):
        db_session.add(OrderItemLedger(
            organization_id=org.id,
            order_id=f"ORD2_{i}",
            order_item_id=f"ITEM2_{i}",
            sku="SKU-NO-RETURNS",
            event_subtype="SALE",
            invoice_amount=200.0,
            order_type="Prepaid",
            customer_delivery_state="Delhi"
        ))

    # Scenario 3: Product with only 1–9 sale items
    for i in range(3):
        db_session.add(OrderItemLedger(
            organization_id=org.id,
            order_id=f"ORD3_{i}",
            order_item_id=f"ITEM3_{i}",
            sku="SKU-TINY",
            event_subtype="SALE",
            invoice_amount=300.0
        ))
        db_session.add(OrderItemLedger(
            organization_id=org.id,
            order_id=f"ORD3_{i}",
            order_item_id=f"ITEM3_{i}",
            sku="SKU-TINY",
            event_subtype="RETURN",
            invoice_amount=300.0
        ))

    # Scenario 7 & 8: Product with missing order type & missing delivery state
    for i in range(12):
        db_session.add(OrderItemLedger(
            organization_id=org.id,
            order_id=f"ORD4_{i}",
            order_item_id=f"ITEM4_{i}",
            sku="SKU-MISSING-FIELDS",
            event_subtype="SALE",
            invoice_amount=400.0,
            order_type=None,
            customer_delivery_state=None
        ))
        if i < 3:
            db_session.add(OrderItemLedger(
                organization_id=org.id,
                order_id=f"ORD4_{i}",
                order_item_id=f"ITEM4_{i}",
                sku="SKU-MISSING-FIELDS",
                event_subtype="RETURN",
                invoice_amount=400.0,
                order_type=None,
                customer_delivery_state=None
            ))

    db_session.commit()

    # 1. Test SKU-DETAIL-1
    res1 = calculation_engine.get_sku_detail(db_session, org.id, "SKU-DETAIL-1")
    assert res1["top_summary"]["sale_items"] == 35
    assert res1["top_summary"]["returned_items"] == 10
    assert res1["top_summary"]["sale_linked_return_rate"] in (28.6, 28.57)
    assert res1["top_summary"]["return_events"] == 10
    assert res1["cancellations"]["cancellation_events"] == 4
    assert res1["cancellations"]["return_cancellation_events"] == 2
    assert res1["data_confidence"] == "GOOD"
    assert res1["status"] == "High Return"

    # 2. Test SKU-NO-RETURNS
    res2 = calculation_engine.get_sku_detail(db_session, org.id, "SKU-NO-RETURNS")
    assert res2["top_summary"]["sale_items"] == 15
    assert res2["top_summary"]["returned_items"] == 0
    assert res2["top_summary"]["sale_linked_return_rate"] == 0.0
    assert res2["status"] == "Healthy"

    # 3. Test SKU-TINY
    res3 = calculation_engine.get_sku_detail(db_session, org.id, "SKU-TINY")
    assert res3["top_summary"]["sale_items"] == 3
    assert res3["top_summary"]["returned_items"] == 3
    assert res3["status"] == "Insufficient Data"
    assert res3["data_confidence"] == "INSUFFICIENT"
    assert "Only 3 sale items were observed" in res3["insight"]["headline"]

    # 4. Test SKU-MISSING-FIELDS
    res4 = calculation_engine.get_sku_detail(db_session, org.id, "SKU-MISSING-FIELDS")
    assert res4["top_summary"]["sale_items"] == 12
    assert res4["top_summary"]["returned_items"] == 3
    assert len(res4["order_type_analysis"]) == 1
    assert res4["order_type_analysis"][0]["order_type"] == "Unknown"
    assert len(res4["state_analysis"]) == 1
    assert res4["state_analysis"][0]["state"] == "Unknown"
