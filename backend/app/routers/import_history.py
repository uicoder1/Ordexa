from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.models import (
    UploadedFile,
    OrderItemLedger,
    CashBackLedger,
    Order,
    Return,
    Settlement,
    Organization,
    User
)
from app.schemas.schemas import UploadedFileResponse
from app.auth.auth import get_current_organization, get_current_user, require_org_role
from app.services.storage import storage_service
from app.services.calculation_engine import calculation_engine
from app.services.audit import audit_service

router = APIRouter(prefix="/imports", tags=["Import History"])

@router.get("", response_model=List[UploadedFileResponse])
def list_import_history(
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    uploads = db.query(UploadedFile).filter(
        UploadedFile.organization_id == current_org.id
    ).order_by(UploadedFile.uploaded_at.desc()).all()
    return uploads

@router.delete("/{upload_id}")
def delete_import_record(
    upload_id: str,
    request: Request,
    current_org: Organization = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    _role_check = Depends(require_org_role("owner")),
    db: Session = Depends(get_db)
):
    """
    Safely deletes an imported file and all associated ledger records within an atomic transaction.
    Restricted strictly to organization owners.
    """
    upload_rec = db.query(UploadedFile).filter(
        UploadedFile.id == upload_id,
        UploadedFile.organization_id == current_org.id
    ).first()

    if not upload_rec:
        raise HTTPException(status_code=404, detail="Upload record not found.")

    filename_meta = upload_rec.filename
    marketplace_meta = upload_rec.marketplace
    storage_path = upload_rec.storage_path
    rows_meta = upload_rec.rows_processed

    try:
        # 1. Delete associated OrderItemLedger rows for that upload (organization-scoped)
        deleted_order_items = db.query(OrderItemLedger).filter(
            OrderItemLedger.upload_id == upload_id,
            OrderItemLedger.organization_id == current_org.id
        ).delete(synchronize_session=False)

        # 2. Delete associated CashBackLedger rows for that upload (organization-scoped)
        deleted_cashbacks = db.query(CashBackLedger).filter(
            CashBackLedger.upload_id == upload_id,
            CashBackLedger.organization_id == current_org.id
        ).delete(synchronize_session=False)

        # 3. Delete associated legacy rows where applicable (organization-scoped)
        db.query(Order).filter(
            Order.upload_id == upload_id,
            Order.organization_id == current_org.id
        ).delete(synchronize_session=False)

        db.query(Return).filter(
            Return.upload_id == upload_id,
            Return.organization_id == current_org.id
        ).delete(synchronize_session=False)

        db.query(Settlement).filter(
            Settlement.upload_id == upload_id,
            Settlement.organization_id == current_org.id
        ).delete(synchronize_session=False)

        # 4. Delete file from storage provider
        storage_service.delete_file(storage_path)

        # 5. Delete UploadedFile record
        db.delete(upload_rec)

        # 6. Recalculate affected SKU metrics
        calculation_engine.calculate_sku_metrics(db, current_org.id)

        # 7. Commit atomic transaction
        db.commit()

        # 8. Record audit log
        audit_service.log_event(
            db=db,
            action="REPORT_DELETED",
            organization_id=current_org.id,
            user_id=current_user.id,
            resource_type="report",
            resource_id=upload_id,
            metadata={
                "filename": filename_meta,
                "marketplace": marketplace_meta,
                "deleted_order_items": deleted_order_items,
                "deleted_cashback_items": deleted_cashbacks,
                "rows_processed": rows_meta
            },
            request=request
        )

        return {
            "message": "Import record and all associated ledger records deleted successfully.",
            "deleted_order_items": deleted_order_items,
            "deleted_cashback_items": deleted_cashbacks
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete import record cleanly: {str(e)}"
        )
