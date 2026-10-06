from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from app.database import get_db
from app.models.models import SKUMetric, Product, Organization, OrderItemLedger, CashBackLedger, Settlement, User
from app.schemas.schemas import SKUMetricResponse
from app.auth.auth import get_current_organization, get_current_user
from app.services.calculation_engine import calculation_engine
from app.services.flipkart_parser import normalize_sku, normalize_product_name
from app.services.audit import audit_service


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/overview")
def get_overview_dashboard(
    request: Request = None,
    current_org: Organization = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Overview Page Endpoint: Returns top KPIs, data period, and unavailability indicators.
    """
    summary = calculation_engine.get_overview_summary(db, current_org.id)
    audit_service.log_event(
        db=db,
        action="FINANCIALS_VIEWED",
        organization_id=current_org.id,
        user_id=current_user.id,
        resource_type="overview_dashboard",
        metadata={"total_orders": summary.get("unique_orders_count"), "sales_value": summary.get("sales_value")},
        request=request
    )
    return summary

@router.get("/debug/overview")
def get_debug_overview(
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    items = db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == current_org.id).all()
    sale_events = [i for i in items if i.event_subtype == "SALE"]
    return_events = [i for i in items if i.event_subtype == "RETURN"]
    cancellation_events = [i for i in items if i.event_subtype == "CANCELLATION"]
    return_cancel_events = [i for i in items if i.event_subtype == "RETURN_CANCELLATION"]

    sale_items = set(i.order_item_id for i in sale_events)
    return_items = set(i.order_item_id for i in return_events)
    sale_and_return_items = len(sale_items.intersection(return_items))

    return {
        "raw_rows": len(items),
        "unique_orders": len(set(i.order_id for i in items)),
        "unique_order_items": len(set(i.order_item_id for i in items)),
        "sale_events": len(sale_events),
        "return_events": len(return_events),
        "cancellation_events": len(cancellation_events),
        "return_cancellation_events": len(return_cancel_events),
        "unique_skus": len(set(i.sku for i in items if i.sku)),
        "sale_items": len(sale_items),
        "return_items": len(return_items),
        "sale_and_return_items": sale_and_return_items
    }

@router.get("/products-needing-attention")
def get_products_needing_attention(
    limit: int = 15,
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """
    "Products Needing Attention" widget on Overview Page.
    Includes status (Healthy, Watch, High Return, Loss Making, Insufficient Data),
    order type breakdown, and delivery state breakdown per product.
    """
    metrics = db.query(SKUMetric).filter(SKUMetric.organization_id == current_org.id).all()
    products = db.query(Product).filter(Product.organization_id == current_org.id).all()
    prod_map = {p.sku: p for p in products}

    ledger_items = db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == current_org.id).all()

    items_by_sku: Dict[str, List[OrderItemLedger]] = {}
    for item in ledger_items:
        s = item.sku.strip().upper()
        if s not in items_by_sku:
            items_by_sku[s] = []
        items_by_sku[s].append(item)

    result = []

    # Priority rule per prompt instructions:
    # 1. Sufficient sample size: >=50 (Tier 0), 30-49 (Tier 1), 10-29 (Tier 2), <10 (Tier 3)
    # 2. Number of returned order items (-m.returned_units)
    # 3. Sale-linked return activity % (-m.sale_linked_return_rate)
    # 4. Return value (-m.return_value)
    def priority_tuple(m: SKUMetric):
        if m.units_sold >= 50:
            sample_tier = 0
        elif m.units_sold >= 30:
            sample_tier = 1
        elif m.units_sold >= 10:
            sample_tier = 2
        else:
            sample_tier = 3

        return (sample_tier, -m.returned_units, -m.sale_linked_return_rate, -m.return_value)

    sorted_metrics = sorted(metrics, key=priority_tuple)

    for m in sorted_metrics[:limit]:
        p = prod_map.get(m.sku)
        s_items = items_by_sku.get(m.sku, [])

        order_types: Dict[str, int] = {}
        states: Dict[str, int] = {}

        for item in s_items:
            ot = item.order_type or "Prepaid"
            order_types[ot] = order_types.get(ot, 0) + (item.quantity or 1)

            st = item.customer_delivery_state or item.customer_billing_state or "Unknown"
            if st and st != "Unknown":
                states[st] = states.get(st, 0) + (item.quantity or 1)

        # Top 3 states
        top_states = sorted(states.items(), key=lambda x: x[1], reverse=True)[:3]
        state_breakdown = ", ".join([f"{st}: {cnt}" for st, cnt in top_states]) or "N/A"

        confidence = getattr(m, "data_confidence", None) or (
            "HIGH" if m.units_sold >= 50 else ("GOOD" if m.units_sold >= 30 else ("MODERATE" if m.units_sold >= 10 else "INSUFFICIENT"))
        )

        result.append({
            "sku": m.sku,
            "product_name": normalize_product_name(p.product_name) if (p and p.product_name) else f"SKU {m.sku}",
            "purchase_cost": p.purchase_cost if p else 0.0,
            "cogs_available": m.cogs_available,
            "sales_count": m.units_sold,
            "sales_revenue": m.revenue,
            "returned_units": m.returned_units,
            "cancellation_units": m.cancellation_units,
            "return_value": m.return_value,
            "sale_linked_return_rate": m.sale_linked_return_rate,
            "data_confidence": confidence,
            "status": m.recommended_action,
            "reason": m.reason,
            "order_type_breakdown": order_types,
            "state_breakdown": state_breakdown
        })

    return result

@router.get("/returns-summary")
@router.get("/returns/summary")
def get_returns_summary(
    request: Request = None,
    current_org: Organization = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns Page Endpoint:
    Top KPI Cards, dynamic Return Timeline, dropdown filter options, and Data Coverage.
    Canonical classification uses Event Sub Type.
    """
    items = db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == current_org.id).all()

    sale_events = [i for i in items if i.event_subtype == "SALE"]
    return_events = [i for i in items if i.event_subtype == "RETURN"]
    cancellation_events = [i for i in items if i.event_subtype == "CANCELLATION"]
    return_cancel_events = [i for i in items if i.event_subtype == "RETURN_CANCELLATION"]

    sale_item_ids = set(i.order_item_id for i in sale_events if i.order_item_id)
    return_item_ids = set(i.order_item_id for i in return_events if i.order_item_id)

    sale_linked_returned_items = len(sale_item_ids.intersection(return_item_ids))
    unique_sale_order_items = len(sale_item_ids)

    sale_linked_return_rate = round(
        (sale_linked_returned_items / unique_sale_order_items * 100.0), 1
    ) if unique_sale_order_items > 0 else 0.0

    returned_value = round(sum(i.invoice_amount or 0.0 for i in return_events), 2)

    # Timeline: Returns by Date (and sale-linked returns)
    timeline_map: Dict[str, Dict[str, Any]] = {}
    for r in return_events:
        if not r.order_date:
            continue
        raw_d = r.order_date.strftime("%Y-%m-%d")
        if raw_d not in timeline_map:
            timeline_map[raw_d] = {
                "date": r.order_date.strftime("%d %b"),
                "raw_date": raw_d,
                "returns": 0,
                "sale_linked_returns": 0
            }
        timeline_map[raw_d]["returns"] += 1
        if r.order_item_id in sale_item_ids:
            timeline_map[raw_d]["sale_linked_returns"] += 1

    timeline_data = [timeline_map[k] for k in sorted(timeline_map.keys())]

    # Unique filter options
    from app.services.flipkart_parser import normalize_sku
    available_skus = sorted(list(set(
        normalize_sku(i.sku) for i in return_events if i.sku and normalize_sku(i.sku)
    )))
    available_order_types = sorted(list(set(
        i.order_type for i in return_events if i.order_type
    )))
    available_states = sorted(list(set(
        (i.customer_delivery_state or i.customer_billing_state or "").strip()
        for i in return_events if (i.customer_delivery_state or i.customer_billing_state)
    )))

    audit_service.log_event(
        db=db,
        action="RETURNS_VIEWED",
        organization_id=current_org.id,
        user_id=current_user.id,
        resource_type="returns_summary",
        metadata={
            "total_return_events": len(return_events),
            "unique_returned_items": len(return_item_ids),
            "returned_value": returned_value
        },
        request=request
    )

    return {
        # Section 2: Top KPI Cards (dynamically computed)
        "total_return_events": len(return_events),
        "unique_returned_order_items": len(return_item_ids),
        "sale_linked_returned_items": sale_linked_returned_items,
        "sale_linked_return_rate": sale_linked_return_rate,
        "returned_value": returned_value,
        "return_cancellations": len(return_cancel_events),

        # Legacy backward-compatibility
        "return_events_count": len(return_events),
        "returned_order_items_count": len(return_item_ids),
        "cancellation_events_count": len(cancellation_events),
        "return_cancellation_events_count": len(return_cancel_events),

        # Section 10: Return Timeline
        "timeline_chart": timeline_data,

        # Filter options for UI dropdowns
        "filter_options": {
            "skus": available_skus,
            "order_types": available_order_types,
            "delivery_states": available_states
        },

        # Section 11: Return Data Coverage
        "data_quality": {
            "return_events_available": True,
            "sale_events_available": True,
            "sale_linked_returns_available": True,
            "return_reason_available": False,
            "return_reason_note": "The current Flipkart Sales Report does not provide an explicit return reason/type."
        }
    }


@router.get("/returns/products")
def get_returns_products_summary(
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """
    Section 5 & 6: Products With Most Returns
    Columns:
      SKU, Product Name, Sale Items, Returned Items, Sale-linked Return %,
      Returned Value, Revenue Generated, Return Rank
    Sort default: Highest returned items
    Descriptive ranking only.
    """
    from collections import defaultdict
    from app.services.flipkart_parser import normalize_sku, normalize_product_name

    items = db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == current_org.id).all()

    sale_items = [i for i in items if i.event_subtype == "SALE"]
    return_events = [i for i in items if i.event_subtype == "RETURN"]

    sku_sales = defaultdict(lambda: {"sale_ids": set(), "revenue": 0.0, "name": ""})
    for s in sale_items:
        sku_c = normalize_sku(s.sku) if s.sku else "UNKNOWN"
        if sku_c:
            sku_upper = sku_c.upper()
            sku_sales[sku_upper]["canonical_sku"] = sku_c
            sku_sales[sku_upper]["sale_ids"].add(s.order_item_id)
            sku_sales[sku_upper]["revenue"] += (s.invoice_amount or 0.0)
            if s.product_name and not sku_sales[sku_upper]["name"]:
                sku_sales[sku_upper]["name"] = normalize_product_name(s.product_name)

    sku_returns = defaultdict(lambda: {"return_ids": set(), "returned_value": 0.0, "name": ""})
    for r in return_events:
        sku_c = normalize_sku(r.sku) if r.sku else "UNKNOWN"
        if sku_c:
            sku_upper = sku_c.upper()
            sku_returns[sku_upper]["canonical_sku"] = sku_c
            sku_returns[sku_upper]["return_ids"].add(r.order_item_id)
            sku_returns[sku_upper]["returned_value"] += (r.invoice_amount or 0.0)
            if r.product_name and not sku_returns[sku_upper]["name"]:
                sku_returns[sku_upper]["name"] = normalize_product_name(r.product_name)

    results = []
    for sku_upper, ret_data in sku_returns.items():
        canonical_sku = ret_data.get("canonical_sku", sku_upper)
        sales_data = sku_sales.get(sku_upper, {"sale_ids": set(), "revenue": 0.0, "name": ""})

        sale_item_count = len(sales_data["sale_ids"])
        returned_item_count = len(ret_data["return_ids"])
        sale_linked_count = len(sales_data["sale_ids"].intersection(ret_data["return_ids"]))

        rate = round((sale_linked_count / sale_item_count * 100.0), 2) if sale_item_count > 0 else 0.0
        product_name = ret_data["name"] or sales_data["name"] or f"SKU {canonical_sku}"

        results.append({
            "sku": canonical_sku,
            "product_name": product_name,
            "sale_items": sale_item_count,
            "returned_items": returned_item_count,
            "sale_linked_returns": sale_linked_count,
            "sale_linked_return_rate": rate,
            "returned_value": round(ret_data["returned_value"], 2),
            "revenue_generated": round(sales_data["revenue"], 2),
        })

    # Sort descending by returned items, then returned value
    results.sort(key=lambda x: (x["returned_items"], x["returned_value"]), reverse=True)
    for rank, p in enumerate(results, 1):
        p["return_rank"] = rank

    return results


@router.get("/returns/orders")
def get_returns_orders_ledger(
    search: Optional[str] = None,
    event: Optional[str] = "RETURN",
    sku: Optional[str] = None,
    order_type: Optional[str] = None,
    delivery_state: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """
    Section 3, 4, 9: All Return Orders ledger table & Order Detail data.
    Event Sub Type is canonical.
    Default event filter: RETURN (can be RETURN_CANCELLATION).
    Never includes CANCELLATION or SALE in this table.
    Includes Sale event linking data (sale_date, sale_value) for order detail modal.
    """
    from app.services.flipkart_parser import normalize_sku, normalize_product_name

    items = db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == current_org.id).all()

    # Pre-build fast lookup for Sale events by Order Item ID
    sale_map: Dict[str, Dict[str, Any]] = {}
    for i in items:
        if i.event_subtype == "SALE" and i.order_item_id:
            if i.order_item_id not in sale_map:
                sale_map[i.order_item_id] = {
                    "sale_date": i.order_date.strftime("%d %b %Y") if i.order_date else "Unknown",
                    "sale_value": round(i.invoice_amount or 0.0, 2)
                }

    target_event = (event or "RETURN").strip().upper()
    if target_event not in ["RETURN", "RETURN_CANCELLATION"]:
        target_event = "RETURN"

    candidate_items = [i for i in items if i.event_subtype == target_event]

    if sku:
        sku_clean = normalize_sku(sku).upper()
        candidate_items = [i for i in candidate_items if i.sku and normalize_sku(i.sku).upper() == sku_clean]

    if order_type and order_type != "ALL":
        candidate_items = [i for i in candidate_items if (i.order_type or "").upper() == order_type.upper()]

    if delivery_state and delivery_state != "ALL":
        target_st = delivery_state.strip().upper()
        candidate_items = [
            i for i in candidate_items
            if (i.customer_delivery_state or i.customer_billing_state or "").strip().upper() == target_st
        ]

    if start_date:
        candidate_items = [i for i in candidate_items if i.order_date and i.order_date.strftime("%Y-%m-%d") >= start_date]

    if end_date:
        candidate_items = [i for i in candidate_items if i.order_date and i.order_date.strftime("%Y-%m-%d") <= end_date]

    if search:
        s = search.lower().strip()
        candidate_items = [
            i for i in candidate_items
            if (i.order_id and s in i.order_id.lower())
            or (i.order_item_id and s in i.order_item_id.lower())
            or (i.sku and s in i.sku.lower())
            or (i.product_name and s in i.product_name.lower())
        ]

    rows = []
    for i in candidate_items:
        has_sale = i.order_item_id in sale_map
        sale_info = sale_map.get(i.order_item_id, {})
        dt_str = i.order_date.strftime("%d %b %Y") if i.order_date else "—"
        state = (i.customer_delivery_state or i.customer_billing_state or i.shipped_from_state or "Unknown").strip()

        rows.append({
            "order_id": i.order_id or "—",
            "order_item_id": i.order_item_id or "—",
            "sku": normalize_sku(i.sku) if i.sku else "—",
            "product_name": normalize_product_name(i.product_name) if i.product_name else (i.sku or "—"),
            "order_date": dt_str,
            "return_date": dt_str,
            "order_type": i.order_type or "—",
            "quantity": i.quantity or 1,
            "return_value": round(i.invoice_amount or 0.0, 2),
            "customer_delivery_state": state,
            "event": "RETURN" if i.event_subtype == "RETURN" else "RETURN CANCELLATION",
            "event_subtype": i.event_subtype,
            "has_sale_event": has_sale,
            "sale_date": sale_info.get("sale_date"),
            "sale_value": sale_info.get("sale_value"),
            "raw_date": i.order_date.strftime("%Y-%m-%d") if i.order_date else ""
        })

    rows.sort(key=lambda x: x["raw_date"], reverse=True)
    return rows

@router.get("/financials-summary")
def get_financials_summary(
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """
    Financials Page Endpoint: Separates marketplace activity from actual profit.
    """
    items = db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == current_org.id).all()
    products = db.query(Product).filter(Product.organization_id == current_org.id).all()
    cb_items = db.query(CashBackLedger).filter(CashBackLedger.organization_id == current_org.id).all()
    has_settlements = db.query(Settlement).filter(Settlement.organization_id == current_org.id).count() > 0
    has_cogs = any(p.purchase_cost and p.purchase_cost > 0 for p in products)

    sale_items = [i for i in items if i.event_subtype == "SALE"]
    total_invoice_amount = sum(i.invoice_amount or 0.0 for i in sale_items)
    total_taxable_value = sum(i.taxable_value or 0.0 for i in sale_items)
    total_discounts = sum(i.discount or 0.0 for i in sale_items)
    total_tcs = sum(i.tcs or 0.0 for i in items) + sum(c.tcs or 0.0 for c in cb_items)
    total_tds = sum(i.tds or 0.0 for i in items) + sum(c.tds or 0.0 for c in cb_items)

    return {
        "cogs_available": has_cogs,
        "cogs_message": "Actual Profit unavailable. Add product costs." if not has_cogs else None,
        "settlement_available": has_settlements,
        "settlement_message": "Settlement reconciliation unavailable. Upload marketplace settlement report." if not has_settlements else None,
        "total_invoice_amount": round(total_invoice_amount, 2),
        "total_taxable_value": round(total_taxable_value, 2),
        "total_discounts": round(total_discounts, 2),
        "total_tcs_deducted": round(total_tcs, 2),
        "total_tds_deducted": round(total_tds, 2),
        "cashback_entries_count": len(cb_items),
        "actual_profit": None if not (has_cogs and has_settlements) else 0.0,
        "net_settlement": None if not has_settlements else 0.0
    }

@router.get("/skus")
def get_products_page_skus(
    search: Optional[str] = None,
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """
    Products Page Grid Endpoint: SKU, Product, Sold Items, Sales, Returned Items,
    Sale-linked Return %, Cancellations, Return Value, COGS, Actual Profit, Margin, Status.
    """
    metrics = db.query(SKUMetric).filter(SKUMetric.organization_id == current_org.id).all()
    products = db.query(Product).filter(Product.organization_id == current_org.id).all()
    prod_map = {p.sku: p for p in products}

    results = []
    for m in metrics:
        p = prod_map.get(m.sku)
        prod_name = normalize_product_name(p.product_name) if (p and p.product_name) else f"SKU {m.sku}"
        cost = p.purchase_cost if p else 0.0

        if search:
            s_low = search.lower()
            if s_low not in m.sku.lower() and s_low not in prod_name.lower():
                continue

        confidence = getattr(m, "data_confidence", None) or (
            "HIGH" if m.units_sold >= 50 else ("GOOD" if m.units_sold >= 30 else ("MODERATE" if m.units_sold >= 10 else "INSUFFICIENT"))
        )

        results.append({
            "sku": m.sku,
            "product_name": prod_name,
            "sold_items": m.units_sold,
            "sales_amount": m.revenue,
            "returned_items": m.returned_units,
            "sale_linked_return_pct": m.sale_linked_return_rate,
            "cancellations": m.cancellation_units,
            "return_value": m.return_value,
            "cogs": cost if cost > 0 else None,
            "cogs_available": m.cogs_available,
            "actual_profit": m.actual_profit,
            "margin_pct": m.profit_margin,
            "data_confidence": confidence,
            "status": m.recommended_action,
            "reason": m.reason
        })

    return sorted(results, key=lambda x: x["sales_amount"], reverse=True)

@router.get("/products/return-ledger")
def get_product_return_ledger(
    sku: str = Query(...),
    order_id: Optional[str] = None,
    order_item_id: Optional[str] = None,
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """
    Returns individual RETURN event records (Event Sub Type = RETURN) for a specific SKU.
    Uses Event Sub Type as the canonical event classifier, not Event Type.
    Return classification is ALWAYS UNKNOWN — Flipkart Sales Report does not provide
    an explicit return reason/type field. We NEVER infer customer return, RTO, or unsold goods.
    """
    from app.services.flipkart_parser import normalize_sku
    sku_canonical = normalize_sku(sku)
    if not sku_canonical:
        return []
    sku_upper = sku_canonical.upper()

    all_items = db.query(OrderItemLedger).filter(
        OrderItemLedger.organization_id == current_org.id
    ).all()

    # Strictly filter on event_subtype = RETURN (not event_type)
    items = [
        i for i in all_items
        if i.sku and normalize_sku(i.sku).upper() == sku_upper
        and i.event_subtype == "RETURN"
    ]

    if order_id:
        items = [i for i in items if order_id.lower() in (i.order_id or "").lower()]
    if order_item_id:
        items = [i for i in items if order_item_id.lower() in (i.order_item_id or "").lower()]

    ledger = []
    for i in items:
        state = (i.customer_delivery_state or i.customer_billing_state or i.shipped_from_state or "Unknown").strip()
        order_date = i.order_date.strftime("%d %b %Y") if i.order_date else "Unknown"
        ledger.append({
            "order_id": i.order_id or "—",
            "order_item_id": i.order_item_id or "—",
            "order_date": order_date,
            "order_type": i.order_type or "—",
            "quantity": i.quantity or 1,
            "invoice_amount": round(i.invoice_amount or 0.0, 2),
            "buyer_invoice_amount": round(i.buyer_invoice_amount or 0.0, 2),
            "customer_delivery_state": state,
            # Return classification: NEVER infer. Flipkart Sales Report has no explicit return reason field.
            "return_reason_note": "Flipkart Sales Report does not provide an explicit return reason/type field. Ordexa does not infer Customer Return, RTO, or Unsold Goods from a generic Return event.",
        })

    ledger.sort(key=lambda x: x["order_date"], reverse=True)
    return ledger


@router.get("/products/cancellation-ledger")
def get_product_cancellation_ledger(
    sku: str = Query(...),
    order_id: Optional[str] = None,
    order_item_id: Optional[str] = None,
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """
    Returns individual CANCELLATION event records (Event Sub Type = Cancellation) for a specific SKU.
    Note: Event Type may say 'Return' but Event Sub Type = Cancellation is the authoritative classifier.
    """
    from app.services.flipkart_parser import normalize_sku
    sku_canonical = normalize_sku(sku)
    if not sku_canonical:
        return []
    sku_upper = sku_canonical.upper()

    all_items = db.query(OrderItemLedger).filter(
        OrderItemLedger.organization_id == current_org.id
    ).all()

    items = [
        i for i in all_items
        if i.sku and normalize_sku(i.sku).upper() == sku_upper
        and i.event_subtype == "CANCELLATION"
    ]

    if order_id:
        items = [i for i in items if order_id.lower() in (i.order_id or "").lower()]
    if order_item_id:
        items = [i for i in items if order_item_id.lower() in (i.order_item_id or "").lower()]

    ledger = []
    for i in items:
        state = (i.customer_delivery_state or i.customer_billing_state or i.shipped_from_state or "Unknown").strip()
        order_date = i.order_date.strftime("%d %b %Y") if i.order_date else "Unknown"
        ledger.append({
            "order_id": i.order_id or "—",
            "order_item_id": i.order_item_id or "—",
            "order_date": order_date,
            "order_type": i.order_type or "—",
            "quantity": i.quantity or 1,
            "invoice_amount": round(i.invoice_amount or 0.0, 2),
            "buyer_invoice_amount": round(i.buyer_invoice_amount or 0.0, 2),
            "customer_delivery_state": state,
        })

    ledger.sort(key=lambda x: x["order_date"], reverse=True)
    return ledger


@router.get("/products/return-cancellation-ledger")
def get_product_return_cancellation_ledger(
    sku: str = Query(...),
    order_id: Optional[str] = None,
    order_item_id: Optional[str] = None,
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """
    Returns individual RETURN CANCELLATION event records (Event Sub Type = Return Cancellation) for a specific SKU.
    These are NOT normal Returns. NOT normal Cancellations. They are separate events.
    """
    from app.services.flipkart_parser import normalize_sku
    sku_canonical = normalize_sku(sku)
    if not sku_canonical:
        return []
    sku_upper = sku_canonical.upper()

    all_items = db.query(OrderItemLedger).filter(
        OrderItemLedger.organization_id == current_org.id
    ).all()

    items = [
        i for i in all_items
        if i.sku and normalize_sku(i.sku).upper() == sku_upper
        and i.event_subtype == "RETURN_CANCELLATION"
    ]

    if order_id:
        items = [i for i in items if order_id.lower() in (i.order_id or "").lower()]
    if order_item_id:
        items = [i for i in items if order_item_id.lower() in (i.order_item_id or "").lower()]

    ledger = []
    for i in items:
        state = (i.customer_delivery_state or i.customer_billing_state or i.shipped_from_state or "Unknown").strip()
        order_date = i.order_date.strftime("%d %b %Y") if i.order_date else "Unknown"
        ledger.append({
            "order_id": i.order_id or "—",
            "order_item_id": i.order_item_id or "—",
            "order_date": order_date,
            "order_type": i.order_type or "—",
            "quantity": i.quantity or 1,
            "invoice_amount": round(i.invoice_amount or 0.0, 2),
            "buyer_invoice_amount": round(i.buyer_invoice_amount or 0.0, 2),
            "customer_delivery_state": state,
        })

    ledger.sort(key=lambda x: x["order_date"], reverse=True)
    return ledger


@router.get("/products/revenue-summary")
def get_product_revenue_summary(
    sku: str = Query(...),
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """
    Returns revenue & sales summary for a specific SKU from Sale events only.
    Event Sub Type = SALE only. Does NOT include Return or Cancellation events.
    Revenue Generated is NOT Profit.
    """
    from app.services.flipkart_parser import normalize_sku
    sku_canonical = normalize_sku(sku)
    if not sku_canonical:
        return {}
    sku_upper = sku_canonical.upper()

    all_items = db.query(OrderItemLedger).filter(
        OrderItemLedger.organization_id == current_org.id
    ).all()

    sku_items = [i for i in all_items if i.sku and normalize_sku(i.sku).upper() == sku_upper]
    sale_events = [i for i in sku_items if i.event_subtype == "SALE"]

    sale_order_item_ids = set(i.order_item_id for i in sale_events)
    units_sold = sum(i.quantity or 1 for i in sale_events)
    revenue = round(sum(i.invoice_amount or 0.0 for i in sale_events), 2)
    sale_items_count = len(sale_order_item_ids)
    avg_revenue = round(revenue / sale_items_count, 2) if sale_items_count > 0 else 0.0

    return {
        "revenue_generated": revenue,
        "sale_items": sale_items_count,
        "units_sold": units_sold,
        "avg_revenue_per_sale_item": avg_revenue,
        "revenue_note": "Revenue Generated is the sum of Final Invoice Amounts for Sale events (Event Sub Type = Sale) only. It is not profit and does not subtract COGS or marketplace costs.",
    }



@router.get("/products/detail")
def get_product_detail_dashboard_by_query(
    sku: str = Query(...),
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """
    Product Detail Page Query Parameter Endpoint (GET /api/v1/dashboard/products/detail?sku=...).
    """
    return calculation_engine.get_sku_detail(db, current_org.id, normalize_sku(sku))

@router.get("/products/{sku}")
def get_product_detail_dashboard(
    sku: str,
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """
    Product Detail Page Endpoint: Returns full normalized ledger analytics, trend charts, order type breakdown,
    state breakdown, deterministic insight panel, and data quality status for a specific SKU.
    """
    return calculation_engine.get_sku_detail(db, current_org.id, normalize_sku(sku))
