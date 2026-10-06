from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import User, Organization, OrganizationMember, OrganizationSubscription, CalculationConfig
from app.schemas.schemas import OrganizationResponse, OrganizationCreate, CalculationConfigResponse, CalculationConfigUpdate
from app.auth.auth import get_current_user, get_current_organization, require_org_role
from app.services.sample_data import sample_data_generator
from app.services.calculation_engine import calculation_engine
from app.services.audit import audit_service

router = APIRouter(prefix="/organizations", tags=["Organizations"])

@router.get("", response_model=List[OrganizationResponse])
def list_my_organizations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    memberships = db.query(OrganizationMember).filter(OrganizationMember.user_id == current_user.id).all()
    org_ids = [m.organization_id for m in memberships]
    orgs = db.query(Organization).filter(Organization.id.in_(org_ids)).all()

    result = []
    for org in orgs:
        mem = next((m for m in memberships if m.organization_id == org.id), None)
        r = OrganizationResponse(
            id=org.id,
            name=org.name,
            owner_id=org.owner_id,
            sales_channels=org.sales_channels or "Amazon,Flipkart,Shopify",
            role=mem.role if mem else "member",
            created_at=org.created_at
        )
        result.append(r)
    return result

@router.post("", response_model=OrganizationResponse)
def create_organization(
    org_in: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    org = Organization(
        name=org_in.name,
        owner_id=current_user.id,
        sales_channels=org_in.sales_channels or "Amazon,Flipkart,Shopify"
    )
    db.add(org)
    db.flush()

    member = OrganizationMember(
        organization_id=org.id,
        user_id=current_user.id,
        role="owner"
    )
    db.add(member)

    sub = OrganizationSubscription(
        organization_id=org.id,
        plan="starter",
        status="active"
    )
    db.add(sub)
    db.commit()
    db.refresh(org)

    # Clean workspace initialization without seeding demo data

    return OrganizationResponse(
        id=org.id,
        name=org.name,
        owner_id=org.owner_id,
        sales_channels=org.sales_channels,
        role="owner",
        created_at=org.created_at
    )

@router.get("/config", response_model=CalculationConfigResponse)
def get_calculation_config(
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    config = calculation_engine.get_or_create_config(db, current_org.id)
    return config

@router.put("/config", response_model=CalculationConfigResponse)
def update_calculation_config(
    config_in: CalculationConfigUpdate,
    request: Request,
    current_org: Organization = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    _role_check = Depends(require_org_role("owner")),
    db: Session = Depends(get_db)
):
    config = calculation_engine.get_or_create_config(db, current_org.id)
    updated_fields = {}
    for field, val in config_in.dict(exclude_unset=True).items():
        setattr(config, field, val)
        updated_fields[field] = val
    db.commit()
    db.refresh(config)

    # Recalculate metrics based on new rules
    calculation_engine.calculate_sku_metrics(db, current_org.id)

    # Audit log
    audit_service.log_event(
        db=db,
        action="SETTINGS_UPDATED",
        organization_id=current_org.id,
        user_id=current_user.id,
        resource_type="organization_config",
        resource_id=config.id,
        metadata={"updated_fields": list(updated_fields.keys())},
        request=request
    )

    return config

@router.post("/seed-demo")
def seed_demo_dataset(
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """
    Injects/resets sample dataset (50-100 SKUs, realistic returns/margin) into the active tenant.
    """
    sample_data_generator.seed_sample_data(db, current_org.id)
    return {"message": f"Sample dataset loaded successfully for {current_org.name}"}
