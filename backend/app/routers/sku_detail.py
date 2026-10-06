from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any

from app.database import get_db
from app.models.models import SKUMetric, Product, Return, Order, Settlement, Organization, CalculationConfig, User
from app.schemas.schemas import SKUDetailResponse, SKUMetricResponse, ProductResponse, ReturnReasonBreakdown, SKUTrendPoint
from app.auth.auth import get_current_organization, get_current_user
from app.services.ai_service import ai_service
from app.services.calculation_engine import calculation_engine
from app.services.flipkart_parser import normalize_sku
from app.services.audit import audit_service

router = APIRouter(prefix="/skus", tags=["SKU Deep Dive Analytics"])

@router.get("/{sku}")
def get_sku_detail(
    sku: str,
    request: Request = None,
    current_org: Organization = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns full normalized ledger analytics, trend charts, order type breakdown,
    state breakdown, deterministic insight panel, and data quality status for a specific SKU.
    """
    clean = normalize_sku(sku)
    audit_service.log_event(
        db=db,
        action="PRODUCT_DETAIL_VIEWED",
        organization_id=current_org.id,
        user_id=current_user.id,
        resource_type="sku",
        resource_id=clean,
        metadata={"sku": clean},
        request=request
    )
    return calculation_engine.get_sku_detail(db, current_org.id, clean)

@router.get("/{sku}/reconciliation")
def get_sku_financial_reconciliation(
    sku: str,
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """
    Requirement #13: Financial Reconciliation View for Auditing Raw Reports.
    Provides line-item mathematical breakdown proving how Revenue, Costs, Fees,
    Settlement, and Profit reconcile down to the exact rupee.
    """
    sku_clean = normalize_sku(sku)
    metric = db.query(SKUMetric).filter(
        SKUMetric.organization_id == current_org.id,
        func.upper(SKUMetric.sku) == sku_clean.upper()
    ).first()

    if not metric:
        calculation_engine.calculate_sku_metrics(db, current_org.id)
        metric = db.query(SKUMetric).filter(
            SKUMetric.organization_id == current_org.id,
            func.upper(SKUMetric.sku) == sku_clean.upper()
        ).first()

    if not metric:
        raise HTTPException(status_code=404, detail="Product not found in the current imported dataset.")

    product = db.query(Product).filter(
        Product.organization_id == current_org.id,
        Product.sku == sku_clean
    ).first()

    orders = db.query(Order).filter(
        Order.organization_id == current_org.id,
        Order.sku == sku_clean
    ).all()

    returns = db.query(Return).filter(
        Return.organization_id == current_org.id,
        Return.sku == sku_clean
    ).all()

    settlements = db.query(Settlement).filter(
        Settlement.organization_id == current_org.id,
        Settlement.sku == sku_clean
    ).all()

    config = calculation_engine.get_or_create_config(db, current_org.id)

    # Line Item Breakdown Table
    breakdown = [
        {"component": "Gross Sales Revenue", "operation": "+", "amount": metric.revenue, "formula": "Units Sold × Selling Price"},
        {"component": "Total Product Purchase Cost", "operation": "-", "amount": metric.total_product_cost, "formula": "Units Sold × Unit Cost"},
        {"component": "Marketplace & Commission Fees", "operation": "-", "amount": metric.marketplace_fees, "formula": "Reported platform referral fees"},
        {"component": "Forward Shipping Charges", "operation": "-", "amount": metric.shipping_cost, "formula": "Delivery courier charges"},
        {"component": "Reverse Shipping / Return Charges", "operation": "-", "amount": metric.return_cost, "formula": "Reverse logistics charges"},
        {"component": "Customer Refunds", "operation": "-", "amount": metric.refund_amount, "formula": "Refunds issued to customers"},
        {"component": "Net Settlement Payout", "operation": "=", "amount": metric.net_settlement, "formula": "Actual bank settlement reported"},
        {"component": "Actual Profit", "operation": "=", "amount": metric.actual_profit, "formula": "Net Settlement - Product Cost - Reverse Logistics"},
        {"component": "Profit Margin", "operation": "=", "amount": f"{metric.profit_margin:.2f}%", "formula": "(Actual Profit / Revenue) × 100"},
    ]

    return {
        "sku": sku_clean,
        "product_name": product.product_name if product else sku_clean,
        "unit_purchase_cost": product.purchase_cost if product else 0.0,
        "summary": {
            "total_orders": metric.total_orders,
            "units_sold": metric.units_sold,
            "returned_units": metric.returned_units,
            "rto_orders": metric.rto_count,
            "return_rate": f"{metric.return_rate:.1f}%",
            "rto_rate": f"{metric.rto_rate:.1f}%",
            "settlement_is_net": config.settlement_is_net
        },
        "reconciliation_breakdown": breakdown,
        "raw_counts": {
            "order_records": len(orders),
            "return_records": len(returns),
            "settlement_records": len(settlements)
        }
    }
