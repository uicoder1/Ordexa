from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.orm import Session
import pandas as pd
import io

from app.database import get_db
from app.models.models import SKUMetric, Product, Organization, User
from app.auth.auth import get_current_organization, get_current_user
from app.services.flipkart_parser import normalize_product_name
from app.services.audit import audit_service

router = APIRouter(prefix="/reports", tags=["Reports & Exports"])

@router.get("/export-sku-profitability")
def export_sku_profitability(
    request: Request = None,
    current_org: Organization = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Exports a comprehensive SKU Profitability CSV report.
    """
    metrics = db.query(SKUMetric).filter(SKUMetric.organization_id == current_org.id).all()
    products = db.query(Product).filter(Product.organization_id == current_org.id).all()
    prod_map = {p.sku: p for p in products}

    data = []
    for m in metrics:
        p = prod_map.get(m.sku)
        prod_name = normalize_product_name(p.product_name) if (p and p.product_name) else f"SKU {m.sku}"
        data.append({
            "SKU": m.sku,
            "Product Name": prod_name,
            "Category": p.category if p else "General",
            "Purchase Cost (INR)": m.total_product_cost / max(1, m.units_sold) if m.total_product_cost else 0.0,
            "Units Sold": m.units_sold,
            "Total Revenue (INR)": m.revenue,
            "Net Settlement (INR)": m.net_settlement,
            "Return Count": m.returns_count,
            "Return Rate (%)": m.return_rate,
            "RTO Count": m.rto_count,
            "RTO Rate (%)": m.rto_rate,
            "Marketplace Fees (INR)": m.marketplace_fees,
            "Return Cost (INR)": m.return_cost,
            "Actual Profit (INR)": m.actual_profit,
            "Profit Margin (%)": m.profit_margin,
            "Estimated Profit Leakage (INR)": m.profit_leakage,
            "Risk Level": m.risk_level,
            "Recommended Action": m.recommended_action
        })

    df = pd.DataFrame(data)
    stream = io.StringIO()
    df.to_csv(stream, index=False)

    audit_service.log_event(
        db=db,
        action="REPORT_EXPORTED",
        organization_id=current_org.id,
        user_id=current_user.id,
        resource_type="report_export",
        metadata={"report_type": "SKU_Profitability", "rows_count": len(metrics)},
        request=request
    )

    safe_org = "".join(c for c in current_org.name if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    return Response(
        content=stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=Ordexa_SKU_Profitability_{safe_org}.csv"}
    )
