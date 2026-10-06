from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import pandas as pd
import io

from app.database import get_db
from app.models.models import Product, Organization, User
from app.schemas.schemas import ProductResponse, ProductCreate, ProductUpdate
from app.auth.auth import get_current_organization, get_current_user, require_org_role
from app.services.calculation_engine import calculation_engine
from app.services.flipkart_parser import normalize_sku, normalize_product_name
from app.services.audit import audit_service

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("", response_model=List[ProductResponse])
def list_products(
    request: Request = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    current_org: Organization = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Product).filter(Product.organization_id == current_org.id)
    if category:
        query = query.filter(Product.category == category)
    if search:
        query = query.filter(
            (Product.sku.ilike(f"%{search}%")) | (Product.product_name.ilike(f"%{search}%"))
        )
    prods = query.order_by(Product.sku).all()

    audit_service.log_event(
        db=db,
        action="PRODUCT_VIEWED",
        organization_id=current_org.id,
        user_id=current_user.id,
        resource_type="product_catalog",
        metadata={"count": len(prods), "search": search, "category": category},
        request=request
    )
    return prods

@router.post("", response_model=ProductResponse)
def create_product(
    prod_in: ProductCreate,
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    existing = db.query(Product).filter(
        Product.organization_id == current_org.id,
        Product.sku == prod_in.sku
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail=f"Product with SKU '{prod_in.sku}' already exists.")

    product = Product(
        organization_id=current_org.id,
        sku=normalize_sku(prod_in.sku),
        product_name=normalize_product_name(prod_in.product_name),
        category=prod_in.category or "General",
        purchase_cost=prod_in.purchase_cost,
        selling_price=prod_in.selling_price or 0.0,
        marketplace=prod_in.marketplace or "All"
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    # Recalculate metrics
    calculation_engine.calculate_sku_metrics(db, current_org.id)

    return product

@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str,
    prod_in: ProductUpdate,
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.organization_id == current_org.id
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    for field, val in prod_in.dict(exclude_unset=True).items():
        if val is not None:
            setattr(product, field, val)

    db.commit()
    db.refresh(product)

    # Recalculate metrics
    calculation_engine.calculate_sku_metrics(db, current_org.id)

    return product

@router.post("/bulk-cost-upload")
def bulk_upload_costs(
    file: UploadFile = File(...),
    request: Request = None,
    current_org: Organization = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    _role_check = Depends(require_org_role("owner", "admin")),
    db: Session = Depends(get_db)
):
    """
    User uploads a SKU & Purchase Cost CSV/Excel file.
    Validates, updates/creates catalog products, commits the transaction, and recalculates metrics.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    ext = file.filename.split(".")[-1].lower()
    if ext not in ["csv", "xlsx", "xls"]:
        raise HTTPException(status_code=400, detail="Only CSV, XLSX, and XLS formats are supported for cost upload.")

    try:
        contents = file.file.read()
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        if ext in ["xlsx", "xls"]:
            df = pd.read_excel(io.BytesIO(contents))
        else:
            df = pd.read_csv(io.BytesIO(contents))

        df = df.fillna("")
        cols = {c.lower().strip(): c for c in df.columns}

        sku_col = cols.get("sku") or cols.get("seller sku") or cols.get("product sku") or cols.get("item sku")
        cost_col = cols.get("purchase cost") or cols.get("cost") or cols.get("unit cost") or cols.get("purchase_cost") or cols.get("cogs")

        if not sku_col or not cost_col:
            raise HTTPException(
                status_code=400,
                detail="File must contain 'SKU' and 'Purchase Cost' columns."
            )

        updated_count = 0
        created_count = 0

        for idx, row in df.iterrows():
            raw_sku = str(row[sku_col]).strip()
            if not raw_sku or raw_sku.lower() in ["nan", "none", "null"]:
                continue

            sku_val = normalize_sku(raw_sku)
            if not sku_val:
                continue

            try:
                cost_val = float(row[cost_col])
                if cost_val < 0:
                    continue
            except (ValueError, TypeError):
                continue

            product = db.query(Product).filter(
                Product.organization_id == current_org.id,
                Product.sku == sku_val
            ).first()

            if product:
                product.purchase_cost = round(cost_val, 2)
                updated_count += 1
            else:
                product = Product(
                    organization_id=current_org.id,
                    sku=sku_val,
                    product_name=f"SKU {sku_val}",
                    category="General",
                    purchase_cost=round(cost_val, 2),
                    selling_price=0.0
                )
                db.add(product)
                created_count += 1

        # 3. Commit the transaction
        db.commit()

        # 4. Recalculate affected SKU metrics
        calculation_engine.calculate_sku_metrics(db, current_org.id)

        # 5. Record Audit Log
        audit_service.log_event(
            db=db,
            action="COGS_UPDATED",
            organization_id=current_org.id,
            user_id=current_user.id,
            resource_type="product",
            metadata={
                "filename": file.filename,
                "updated_products": updated_count,
                "created_products": created_count,
                "total_processed": updated_count + created_count
            },
            request=request
        )

        # 6. Return clear success response
        return {
            "message": "Product costs updated and financial metrics recalculated successfully.",
            "updated_products": updated_count,
            "created_products": created_count,
            "total_processed": updated_count + created_count
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to process cost file. Please check file format.")

@router.post("/update-sku-cost")
def update_sku_cost(
    sku: str,
    purchase_cost: float,
    request: Request = None,
    current_org: Organization = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    _role_check = Depends(require_org_role("owner", "admin")),
    db: Session = Depends(get_db)
):
    sku_clean = normalize_sku(sku)
    product = db.query(Product).filter(
        Product.organization_id == current_org.id,
        Product.sku == sku_clean
    ).first()

    if not product:
        product = Product(
            organization_id=current_org.id,
            sku=sku_clean,
            product_name=f"SKU {sku_clean}",
            category="General",
            purchase_cost=purchase_cost,
            selling_price=0.0
        )
        db.add(product)
    else:
        product.purchase_cost = purchase_cost

    db.commit()
    db.refresh(product)

    calculation_engine.calculate_sku_metrics(db, current_org.id)

    audit_service.log_event(
        db=db,
        action="COGS_UPDATED",
        organization_id=current_org.id,
        user_id=current_user.id,
        resource_type="product",
        resource_id=product.id,
        metadata={"sku": sku_clean, "purchase_cost": purchase_cost},
        request=request
    )

    return {"message": f"Updated purchase cost for SKU '{sku_clean}' to {purchase_cost}", "sku": sku_clean, "purchase_cost": purchase_cost}

