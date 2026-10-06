from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import OrganizationSubscription, Organization, SKUMetric, UploadedFile
from app.auth.auth import get_current_organization

router = APIRouter(prefix="/subscription", tags=["Subscription & Usage Limits"])

PLANS_SPEC = {
    "free": {"name": "Free Tier", "price_inr": 0, "max_uploads": 5, "max_txns": 1000, "max_skus": 50},
    "starter": {"name": "Starter Plan", "price_inr": 199, "max_uploads": 50, "max_txns": 10000, "max_skus": 500},
    "growth": {"name": "Growth Plan", "price_inr": 499, "max_uploads": 200, "max_txns": 50000, "max_skus": 2500},
    "pro": {"name": "Pro Plan", "price_inr": 999, "max_uploads": 1000, "max_txns": 250000, "max_skus": 10000},
}

@router.get("/status")
def get_subscription_status(
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    sub = db.query(OrganizationSubscription).filter(
        OrganizationSubscription.organization_id == current_org.id
    ).first()

    if not sub:
        sub = OrganizationSubscription(
            organization_id=current_org.id,
            plan="starter",
            status="active"
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)

    plan_info = PLANS_SPEC.get(sub.plan.lower(), PLANS_SPEC["starter"])

    # Count current usage
    current_skus = db.query(SKUMetric).filter(SKUMetric.organization_id == current_org.id).count()
    current_uploads = db.query(UploadedFile).filter(UploadedFile.organization_id == current_org.id).count()

    return {
        "organization_id": current_org.id,
        "plan_key": sub.plan,
        "plan_name": plan_info["name"],
        "price_inr": plan_info["price_inr"],
        "status": sub.status,
        "billing_cycle": sub.billing_cycle,
        "usage": {
            "skus_used": current_skus,
            "max_skus": plan_info["max_skus"],
            "uploads_used": current_uploads,
            "max_uploads": plan_info["max_uploads"]
        },
        "available_plans": PLANS_SPEC
    }
