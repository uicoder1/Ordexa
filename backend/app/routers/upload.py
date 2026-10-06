import os
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Request
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Tuple
import json
import re

from app.config import settings
from app.database import get_db
from app.models.models import UploadedFile, OrderItemLedger, CashBackLedger, Product, Organization, Order, Return, Settlement, User
from app.schemas.schemas import UploadedFileResponse, ColumnMappingRequest
from app.auth.auth import get_current_organization, get_current_user, require_org_role
from app.services.storage import storage_service
from app.services.file_parser import file_parser, STANDARD_FIELDS
from app.services.flipkart_parser import flipkart_parser, clean_sku, normalize_product_name
from app.services.calculation_engine import calculation_engine
from app.services.audit import audit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["File Upload Pipeline"])


def _execute_report_import(
    db: Session,
    current_org: Organization,
    upload_rec: UploadedFile,
    abs_path: str,
    marketplace: str = "Flipkart",
    mapping: Optional[dict] = None,
    deduplication_mode: str = "replace"
) -> Tuple[int, int]:
    """
    Parses the marketplace report from the temporary file, populates the PostgreSQL
    ledger and product catalog, recalculates SKU metrics, and updates the upload record.
    Returns (processed_sales_count, processed_cashbacks_count).
    """
    # 1. Parse Flipkart or generic spreadsheet workbook
    sales_records, cashback_records = flipkart_parser.parse_flipkart_workbook(abs_path, upload_rec.file_type)

    if not sales_records and not cashback_records:
        # Fallback to standard generic CSV loader if mapping is available
        generic_recs = file_parser.load_normalized_rows(abs_path, upload_rec.file_type, mapping or {})
        sales_records = []
        for idx, rec in enumerate(generic_recs):
            sku_c = clean_sku(rec.get("sku"))
            if not sku_c:
                continue
            sales_records.append({
                "order_id": str(rec.get("order_id") or f"ORD-{idx+1}"),
                "order_item_id": str(rec.get("order_id") or f"ITEM-{idx+1}"),
                "sku": sku_c,
                "product_name": normalize_product_name(rec.get("product_name")) or f"SKU {sku_c}",
                "event_type": "Order",
                "event_subtype": "SALE",
                "quantity": int(rec.get("quantity") or 1),
                "invoice_amount": float(rec.get("selling_price") or 0.0),
                "shipping_charge": float(rec.get("shipping_charge") or 0.0),
                "marketplace": marketplace
            })

    if not sales_records and not cashback_records:
        raise HTTPException(
            status_code=400,
            detail="Unable to process this report. Please check that it is a valid marketplace report."
        )

    # 2. Wipe old ledger data if replace mode
    if deduplication_mode == "replace":
        db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == current_org.id).delete(synchronize_session=False)
        db.query(CashBackLedger).filter(CashBackLedger.organization_id == current_org.id).delete(synchronize_session=False)
        db.commit()

    processed_sales = 0
    processed_cashbacks = 0

    # 3. Insert Sales records into OrderItemLedger & Product Catalog
    existing_products = {p.sku: p for p in db.query(Product).filter(Product.organization_id == current_org.id).all()}

    new_ledger_items = []
    for rec in sales_records:
        sku_c = rec["sku"]
        if not sku_c:
            continue

        p_name_clean = normalize_product_name(rec.get("product_name")) or f"SKU {sku_c}"

        if sku_c not in existing_products:
            new_p = Product(
                organization_id=current_org.id,
                sku=sku_c,
                product_name=p_name_clean,
                category="General",
                purchase_cost=0.0,
                selling_price=rec.get("price_before_discount") or rec.get("invoice_amount") or 0.0,
                marketplace=marketplace
            )
            db.add(new_p)
            existing_products[sku_c] = new_p

        ledger_item = OrderItemLedger(
            organization_id=current_org.id,
            upload_id=upload_rec.id,
            seller_gstin=rec.get("seller_gstin"),
            order_id=rec["order_id"],
            order_item_id=rec["order_item_id"],
            product_name=p_name_clean,
            fsn=rec.get("fsn"),
            sku=sku_c,
            hsn_code=rec.get("hsn_code"),
            event_type=rec.get("event_type"),
            event_subtype=rec.get("event_subtype", "SALE"),
            order_type=rec.get("order_type"),
            fulfilment_type=rec.get("fulfilment_type"),
            order_date=rec.get("order_date"),
            order_approval_date=rec.get("order_approval_date"),
            quantity=rec.get("quantity", 1),
            shipped_from_state=rec.get("shipped_from_state"),
            warehouse_id=rec.get("warehouse_id"),
            price_before_discount=rec.get("price_before_discount", 0.0),
            discount=rec.get("discount", 0.0),
            seller_share=rec.get("seller_share", 0.0),
            bank_offer_share=rec.get("bank_offer_share", 0.0),
            price_after_discount=rec.get("price_after_discount", 0.0),
            shipping_charge=rec.get("shipping_charge", 0.0),
            invoice_amount=rec.get("invoice_amount", 0.0),
            taxable_value=rec.get("taxable_value", 0.0),
            igst_rate=rec.get("igst_rate", 0.0),
            igst_amount=rec.get("igst_amount", 0.0),
            cgst_rate=rec.get("cgst_rate", 0.0),
            cgst_amount=rec.get("cgst_amount", 0.0),
            sgst_rate=rec.get("sgst_rate", 0.0),
            sgst_amount=rec.get("sgst_amount", 0.0),
            tcs=rec.get("tcs", 0.0),
            tds=rec.get("tds", 0.0),
            buyer_invoice_id=rec.get("buyer_invoice_id"),
            buyer_invoice_date=rec.get("buyer_invoice_date"),
            buyer_invoice_amount=rec.get("buyer_invoice_amount", 0.0),
            customer_billing_pincode=rec.get("customer_billing_pincode"),
            customer_billing_state=rec.get("customer_billing_state"),
            customer_delivery_pincode=rec.get("customer_delivery_pincode"),
            customer_delivery_state=rec.get("customer_delivery_state"),
            usual_price=rec.get("usual_price", 0.0),
            is_shopsy=rec.get("is_shopsy", False),
            marketplace=marketplace
        )
        new_ledger_items.append(ledger_item)
        processed_sales += 1

    db.add_all(new_ledger_items)

    # 4. Insert Cashback records into CashBackLedger
    new_cb_items = []
    for rec in cashback_records:
        cb_item = CashBackLedger(
            organization_id=current_org.id,
            upload_id=upload_rec.id,
            seller_gstin=rec.get("seller_gstin"),
            order_id=rec["order_id"],
            order_item_id=rec["order_item_id"],
            document_type=rec.get("document_type"),
            document_subtype=rec.get("document_subtype"),
            credit_debit_note_id=rec.get("credit_debit_note_id"),
            invoice_amount=rec.get("invoice_amount", 0.0),
            invoice_date=rec.get("invoice_date"),
            taxable_value=rec.get("taxable_value", 0.0),
            igst_amount=rec.get("igst_amount", 0.0),
            cgst_amount=rec.get("cgst_amount", 0.0),
            sgst_amount=rec.get("sgst_amount", 0.0),
            tcs=rec.get("tcs", 0.0),
            tds=rec.get("tds", 0.0),
            customer_delivery_state=rec.get("customer_delivery_state"),
            is_shopsy=rec.get("is_shopsy", False)
        )
        new_cb_items.append(cb_item)
        processed_cashbacks += 1

    db.add_all(new_cb_items)

    upload_rec.upload_status = "completed"
    upload_rec.rows_processed = processed_sales + processed_cashbacks
    db.commit()

    # 5. Recalculate SKUMetrics
    calculation_engine.calculate_sku_metrics(db, current_org.id)

    return (processed_sales, processed_cashbacks)


@router.post("/file")
def upload_report_file(
    request: Request,
    file: UploadFile = File(...),
    marketplace: str = Form("Flipkart"),
    current_org: Organization = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    _role_check = Depends(require_org_role("owner", "admin")),
    db: Session = Depends(get_db)
):
    # 1. Safe filename handling & path traversal protection
    raw_name = (file.filename or "").replace("\\", "/")
    safe_filename = os.path.basename(raw_name).strip()
    safe_filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', safe_filename)
    if not safe_filename or safe_filename in [".", ".."]:
        safe_filename = "report_upload.xlsx"

    ext = safe_filename.split(".")[-1].lower() if "." in safe_filename else ""
    if ext not in ["csv", "xlsx", "xls"]:
        raise HTTPException(
            status_code=400,
            detail="Please upload an Excel or CSV report."
        )

    # 2. Maximum upload size pre-validation via Content-Length header
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise HTTPException(
                    status_code=400,
                    detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB."
                )
        except ValueError:
            pass

    # 3. MIME/content header validation (magic bytes)
    header_bytes = file.file.read(512)
    file.file.seek(0)

    if ext == "xlsx":
        if not header_bytes.startswith(b"PK\x03\x04"):
            raise HTTPException(status_code=400, detail="Unable to process this report. Please check that it is a valid marketplace report.")
    elif ext == "xls":
        if not header_bytes.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            raise HTTPException(status_code=400, detail="Unable to process this report. Please check that it is a valid marketplace report.")
    elif ext == "csv":
        if b"\x00" in header_bytes:
            raise HTTPException(status_code=400, detail="Unable to process this report. Please check that it is a valid marketplace report.")

    # Audit upload start
    audit_service.log_event(
        db=db,
        action="REPORT_UPLOAD_STARTED",
        organization_id=current_org.id,
        user_id=current_user.id,
        resource_type="report",
        metadata={"filename": safe_filename, "marketplace": marketplace, "ext": ext},
        request=request
    )

    # 4. Save file temporarily using storage provider
    file.filename = safe_filename
    rel_path = storage_service.save_file(current_org.id, file)
    file_size = storage_service.get_file_size(rel_path)

    if file_size > max_bytes:
        storage_service.delete_file(rel_path)
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB."
        )

    abs_path = storage_service.get_absolute_path(rel_path)

    try:
        # Detect Flipkart reports & sheets if applicable
        detect_info = flipkart_parser.detect_sheets_and_report_types(abs_path, ext)
        headers, preview_rows, total_rows = file_parser.read_file_preview(abs_path, ext)

        missing_warnings = []
        cogs_exists = db.query(Product).filter(Product.organization_id == current_org.id, Product.purchase_cost > 0).count() > 0
        if not cogs_exists:
            missing_warnings.append("COGS")
        if not detect_info.get("has_settlement_report"):
            missing_warnings.append("Settlement")
        missing_warnings.append("RTO status")

        upload_rec = UploadedFile(
            organization_id=current_org.id,
            filename=safe_filename,
            marketplace=marketplace,
            storage_path=rel_path,
            file_type=ext,
            file_size=file_size,
            upload_status="uploaded",
            rows_processed=detect_info.get("total_rows") or total_rows,
            uploaded_at=datetime.utcnow()
        )
        db.add(upload_rec)
        db.commit()
        db.refresh(upload_rec)

        # 5. Process immediately while the temporary file is active on disk
        # This completely removes any dependency on Render's ephemeral filesystem!
        has_marketplace_data = (
            detect_info.get("sales_count", 0) > 0 or
            detect_info.get("returns_count", 0) > 0 or
            detect_info.get("cancellations_count", 0) > 0
        )
        auto_mapping = file_parser.auto_detect_mapping(headers)

        if has_marketplace_data or (auto_mapping.get("sku") and auto_mapping.get("order_id")):
            try:
                processed_sales, processed_cashbacks = _execute_report_import(
                    db=db,
                    current_org=current_org,
                    upload_rec=upload_rec,
                    abs_path=abs_path,
                    marketplace=marketplace,
                    mapping=auto_mapping,
                    deduplication_mode="replace"
                )

                # Safe cleanup: Delete temporary file now that records and SKUMetrics are safely in PostgreSQL
                storage_service.delete_file(upload_rec.storage_path)

                # Audit processing completed
                audit_service.log_event(
                    db=db,
                    action="REPORT_PROCESSING_COMPLETED",
                    organization_id=current_org.id,
                    user_id=current_user.id,
                    resource_type="report",
                    resource_id=upload_rec.id,
                    metadata={
                        "upload_id": upload_rec.id,
                        "processed_rows": processed_sales + processed_cashbacks,
                        "sales_count": processed_sales,
                        "cashback_count": processed_cashbacks
                    },
                    request=request
                )
            except HTTPException:
                storage_service.delete_file(upload_rec.storage_path)
                raise
            except Exception as e:
                logger.exception(f"Error processing upload {upload_rec.id}: {e}")
                db.rollback()
                upload_rec.upload_status = "failed"
                upload_rec.error_message = str(e)
                db.commit()
                storage_service.delete_file(upload_rec.storage_path)
                raise HTTPException(
                    status_code=400,
                    detail="We couldn't analyze this report. Please try again."
                )

        # Audit upload completed
        audit_service.log_event(
            db=db,
            action="REPORT_UPLOADED",
            organization_id=current_org.id,
            user_id=current_user.id,
            resource_type="report",
            resource_id=upload_rec.id,
            metadata={
                "filename": safe_filename,
                "marketplace": marketplace,
                "file_size": file_size,
                "rows_detected": detect_info.get("total_rows") or total_rows
            },
            request=request
        )

        return {
            "upload_id": upload_rec.id,
            "filename": file.filename,
            "marketplace": marketplace,
            "file_size_bytes": file_size,
            "total_rows_detected": detect_info.get("total_rows") or total_rows,
            "headers": headers,
            "auto_mapping": auto_mapping,
            "standard_fields": STANDARD_FIELDS,
            "preview_rows": preview_rows,
            "detection_summary": {
                "rows_count": detect_info.get("total_rows") or total_rows,
                "orders_count": detect_info.get("orders_count", 0),
                "skus_count": detect_info.get("skus_count", 0),
                "sales_detected": detect_info.get("sales_count", 0) > 0,
                "returns_detected": detect_info.get("returns_count", 0) > 0,
                "cancellations_detected": detect_info.get("cancellations_count", 0) > 0,
                "customer_states_detected": detect_info.get("customer_states_detected", False),
                "detected_reports": detect_info.get("detected_reports", []),
                "missing_warnings": missing_warnings
            }
        }
    except HTTPException:
        storage_service.delete_file(rel_path)
        raise
    except Exception as e:
        storage_service.delete_file(rel_path)
        logger.exception(f"Failed to inspect uploaded report {safe_filename}: {e}")
        raise HTTPException(
            status_code=400,
            detail="Unable to process this report. Please check that it is a valid marketplace report."
        )


@router.post("/process-mapping")
def process_mapped_file(
    req: ColumnMappingRequest,
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    upload_rec = db.query(UploadedFile).filter(
        UploadedFile.id == req.upload_id,
        UploadedFile.organization_id == current_org.id
    ).first()

    if not upload_rec:
        raise HTTPException(status_code=404, detail="Upload record not found.")

    # If the upload has already been processed into PostgreSQL (zero ephemeral disk dependency)
    if upload_rec.upload_status == "completed":
        sales_count = db.query(OrderItemLedger).filter(
            OrderItemLedger.organization_id == current_org.id,
            OrderItemLedger.upload_id == upload_rec.id
        ).count()
        cb_count = db.query(CashBackLedger).filter(
            CashBackLedger.organization_id == current_org.id,
            CashBackLedger.upload_id == upload_rec.id
        ).count()
        processed_rows = upload_rec.rows_processed or (sales_count + cb_count)

        return {
            "message": f"Successfully imported {sales_count} sales/return records and {cb_count} cash back records.",
            "processed_rows": processed_rows,
            "sales_records_count": sales_count,
            "cashback_records_count": cb_count,
            "upload_id": upload_rec.id
        }

    # If not already completed, process now if the temporary file exists
    abs_path = storage_service.get_absolute_path(upload_rec.storage_path)
    if not os.path.exists(abs_path):
        logger.error(f"Temporary file {abs_path} missing for pending upload {upload_rec.id}")
        raise HTTPException(
            status_code=400,
            detail="Unable to process this report. Please upload the file again."
        )

    upload_rec.column_mapping = json.dumps(req.mapping)
    upload_rec.upload_status = "processing"
    db.commit()

    try:
        processed_sales, processed_cashbacks = _execute_report_import(
            db=db,
            current_org=current_org,
            upload_rec=upload_rec,
            abs_path=abs_path,
            marketplace=req.marketplace,
            mapping=req.mapping,
            deduplication_mode=req.deduplication_mode
        )

        # Clean up temporary file now that records are stored in PostgreSQL
        storage_service.delete_file(upload_rec.storage_path)

        # Audit log processing success
        audit_service.log_event(
            db=db,
            action="REPORT_PROCESSING_COMPLETED",
            organization_id=current_org.id,
            user_id=upload_rec.organization.owner_id if hasattr(upload_rec, 'organization') and upload_rec.organization else None,
            resource_type="report",
            resource_id=upload_rec.id,
            metadata={
                "upload_id": upload_rec.id,
                "processed_rows": processed_sales + processed_cashbacks,
                "sales_count": processed_sales,
                "cashback_count": processed_cashbacks
            }
        )

        return {
            "message": f"Successfully imported {processed_sales} sales/return records and {processed_cashbacks} cash back records.",
            "processed_rows": processed_sales + processed_cashbacks,
            "sales_records_count": processed_sales,
            "cashback_records_count": processed_cashbacks,
            "upload_id": upload_rec.id
        }

    except HTTPException:
        storage_service.delete_file(upload_rec.storage_path)
        raise
    except Exception as e:
        logger.exception(f"Report processing failed for {upload_rec.id}: {e}")
        db.rollback()
        upload_rec.upload_status = "failed"
        upload_rec.error_message = str(e)
        db.commit()
        storage_service.delete_file(upload_rec.storage_path)

        # Audit log processing failure
        audit_service.log_event(
            db=db,
            action="REPORT_PROCESSING_FAILED",
            organization_id=current_org.id,
            resource_type="report",
            resource_id=upload_rec.id,
            metadata={"upload_id": upload_rec.id, "error": str(e)[:200]}
        )

        raise HTTPException(
            status_code=400,
            detail="We couldn't analyze this report. Please try again."
        )
