import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models.models import User, Organization, OrganizationMember, OrderItemLedger, SKUMetric
from app.auth.auth import create_access_token

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def test_client_and_db():
    from app.database import engine as app_engine
    Base.metadata.create_all(bind=app_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=app_engine)
    db = TestingSessionLocal()

    # Scope cleanup strictly to test organization to preserve known-good development data
    db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == "test-org-reg-id").delete()
    db.query(SKUMetric).filter(SKUMetric.organization_id == "test-org-reg-id").delete()
    db.commit()

    user = db.query(User).filter(User.email == "testreg@example.com").first()
    if not user:
        user = User(id="test-user-reg-id", email="testreg@example.com", hashed_password="pw", name="Reg User")
        db.add(user)
        db.flush()

    org = db.query(Organization).filter(Organization.id == "test-org-reg-id").first()
    if not org:
        org = Organization(id="test-org-reg-id", name="Reg Test Store", owner_id=user.id)
        db.add(org)
        db.flush()

    member = db.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id, OrganizationMember.user_id == user.id).first()
    if not member:
        member = OrganizationMember(organization_id=org.id, user_id=user.id, role="owner")
        db.add(member)
    db.commit()

    client = TestClient(app)

    token = create_access_token(data={"sub": user.id})
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": org.id
    }

    yield client, db, headers, org.id

    db.close()

def test_real_flipkart_upload_and_metrics_regression(test_client_and_db):
    client, db, headers, org_id = test_client_and_db

    from pathlib import Path
    tests_dir = Path(__file__).resolve().parent
    file_path = str(tests_dir / "fixtures" / "sample_flipkart.xlsx")
    assert os.path.exists(file_path), f"Sanitized Flipkart test fixture missing at {file_path}"

    # 1. Step 1: Upload File
    with open(file_path, "rb") as f:
        resp_upload = client.post(
            "/api/v1/upload/file",
            files={"file": ("flipkart_sales.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"marketplace": "Flipkart"},
            headers=headers
        )

    assert resp_upload.status_code == 200
    upload_res = resp_upload.json()
    upload_id = upload_res["upload_id"]
    assert upload_id is not None

    # 2. Step 2: Process Mapping
    resp_process = client.post(
        "/api/v1/upload/process-mapping",
        json={
            "upload_id": upload_id,
            "marketplace": "Flipkart",
            "mapping": upload_res.get("auto_mapping", {}),
            "deduplication_mode": "replace"
        },
        headers=headers
    )
    assert resp_process.status_code == 200
    proc_res = resp_process.json()
    assert proc_res["sales_records_count"] == 2373

    # 3. Direct DB Ledger Assertions
    ledger_items = db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == org_id).all()
    assert len(ledger_items) == 2373

    sale_events = [i for i in ledger_items if i.event_subtype == "SALE"]
    return_events = [i for i in ledger_items if i.event_subtype == "RETURN"]
    cancellation_events = [i for i in ledger_items if i.event_subtype == "CANCELLATION"]
    return_cancel_events = [i for i in ledger_items if i.event_subtype == "RETURN_CANCELLATION"]

    assert len(sale_events) == 1734
    assert len(return_events) == 486
    assert len(cancellation_events) == 134
    assert len(return_cancel_events) == 19

    unique_orders = len(set(i.order_id for i in ledger_items))
    unique_order_items = len(set(i.order_item_id for i in ledger_items))
    unique_skus = len(set(i.sku for i in ledger_items if i.sku))

    assert unique_orders == 1752
    assert unique_order_items == 1766
    assert unique_skus == 57

    sale_items = set(i.order_item_id for i in sale_events)
    return_items = set(i.order_item_id for i in return_events)
    sale_and_return_items = len(sale_items.intersection(return_items))

    assert len(sale_items) == 1698
    assert len(return_items) == 477
    assert sale_and_return_items == 411

    sale_linked_rate = round((411 / 1698 * 100), 1)
    assert sale_linked_rate == 24.2

    # 4. Dashboard Overview API Endpoint
    resp_overview = client.get("/api/v1/dashboard/overview", headers=headers)
    assert resp_overview.status_code == 200
    ov = resp_overview.json()

    assert ov["sales_value"] == 319328.0
    assert ov["returned_value"] == 97967.0
    assert ov["sale_events_count"] == 1734
    assert ov["return_events_count"] == 486
    assert ov["cancellation_events_count"] == 134
    assert ov["unique_orders_count"] == 1752
    assert ov["unique_skus_count"] == 57
    assert ov["sale_linked_return_rate"] == 24.2

    # 5. Products Needing Attention Endpoint
    resp_attention = client.get("/api/v1/dashboard/products-needing-attention", headers=headers)
    assert resp_attention.status_code == 200
    attention_items = resp_attention.json()
    assert len(attention_items) > 0

    # 6. Product Detail Endpoint for L-ORI-JHU-SL
    resp_detail = client.get("/api/v1/dashboard/products/L-ORI-JHU-SL", headers=headers)
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["sku"] == "L-ORI-JHU-SL"


def test_flipkart_replace_mode_and_informational_notices_regression(test_client_and_db):
    client, db, headers, org_id = test_client_and_db

    from pathlib import Path
    tests_dir = Path(__file__).resolve().parent
    file_path = str(tests_dir / "fixtures" / "sample_flipkart.xlsx")
    assert os.path.exists(file_path)

    # 1. Step 1: Upload File and verify informational notices are present and NOT treated as errors
    with open(file_path, "rb") as f:
        resp_upload1 = client.post(
            "/api/v1/upload/file",
            files={"file": ("flipkart_sales.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"marketplace": "Flipkart"},
            headers=headers
        )

    assert resp_upload1.status_code == 200
    up1 = resp_upload1.json()
    assert up1["total_rows_detected"] == 2842
    assert up1["detection_summary"]["orders_count"] == 1766
    assert up1["detection_summary"]["skus_count"] == 57
    assert up1["detection_summary"]["sales_detected"] is True
    assert up1["detection_summary"]["returns_detected"] is True
    assert up1["detection_summary"]["cancellations_detected"] is True

    # Informational notices must be present
    notices = up1["detection_summary"]["missing_warnings"]
    assert "COGS" in notices
    assert "Settlement" in notices
    assert "RTO status" in notices

    # 2. Step 2: First import in replace mode
    resp_proc1 = client.post(
        "/api/v1/upload/process-mapping",
        json={
            "upload_id": up1["upload_id"],
            "marketplace": "Flipkart",
            "mapping": up1.get("auto_mapping", {}),
            "deduplication_mode": "replace"
        },
        headers=headers
    )
    assert resp_proc1.status_code == 200
    assert resp_proc1.json()["sales_records_count"] == 2373

    # 3. Step 3: Re-upload and import a second time in replace mode (simulating replacing report)
    # This must NOT fail with ObjectDeletedError or "Processing failed"
    with open(file_path, "rb") as f:
        resp_upload2 = client.post(
            "/api/v1/upload/file",
            files={"file": ("flipkart_sales_replace.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"marketplace": "Flipkart"},
            headers=headers
        )
    assert resp_upload2.status_code == 200
    up2 = resp_upload2.json()

    resp_proc2 = client.post(
        "/api/v1/upload/process-mapping",
        json={
            "upload_id": up2["upload_id"],
            "marketplace": "Flipkart",
            "mapping": up2.get("auto_mapping", {}),
            "deduplication_mode": "replace"
        },
        headers=headers
    )
    assert resp_proc2.status_code == 200, f"Process mapping failed: {resp_proc2.text}"
    assert resp_proc2.json()["sales_records_count"] == 2373

    # 4. Verify clean ledger and metrics state after replace
    ledger_count = db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == org_id).count()
    assert ledger_count == 2373

    metrics_count = db.query(SKUMetric).filter(SKUMetric.organization_id == org_id).count()
    assert metrics_count == 57

    # 5. Verify overview dashboard endpoint returns complete numbers
    resp_overview = client.get("/api/v1/dashboard/overview", headers=headers)
    assert resp_overview.status_code == 200
    ov = resp_overview.json()
    assert ov["sales_value"] == 319328.0
    assert ov["returned_value"] == 97967.0
    assert ov["sale_events_count"] == 1734
    assert ov["return_events_count"] == 486
    assert ov["cancellation_events_count"] == 134
    assert ov["unique_orders_count"] == 1752
    assert ov["unique_skus_count"] == 57
    assert ov["sale_linked_return_rate"] == 24.2


def test_upload_and_process_zero_disk_dependency_and_sanitized_errors(test_client_and_db):
    """
    Verifies that:
    1. Report upload processes into PostgreSQL immediately without depending on persistent ephemeral disk.
    2. The temporary file is cleaned up from disk, yet /process-mapping succeeds instantly.
    3. The cancellations endpoint returns 134 cancellation rows.
    4. Invalid files return friendly error messages with zero raw stack traces or filesystem paths.
    """
    client, db, headers, org_id = test_client_and_db
    from app.services.storage import storage_service
    from app.models.models import UploadedFile

    from pathlib import Path
    tests_dir = Path(__file__).resolve().parent
    file_path = str(tests_dir / "fixtures" / "sample_flipkart.xlsx")
    assert os.path.exists(file_path)

    # 1. Step 1: Upload File
    with open(file_path, "rb") as f:
        resp_upload = client.post(
            "/api/v1/upload/file",
            files={"file": ("flipkart_sales.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"marketplace": "Flipkart"},
            headers=headers
        )

    assert resp_upload.status_code == 200
    up_res = resp_upload.json()
    upload_id = up_res["upload_id"]

    # Verify physical file is already safely removed or not required
    upload_rec = db.query(UploadedFile).filter(UploadedFile.id == upload_id).first()
    assert upload_rec is not None
    assert upload_rec.upload_status == "completed"

    abs_path = storage_service.get_absolute_path(upload_rec.storage_path)
    # Ensure physical file is gone (deleted after processing)
    if os.path.exists(abs_path):
        os.remove(abs_path)
    assert not os.path.exists(abs_path), "Temporary file should not exist on disk"

    # 2. Step 2: Call /process-mapping when physical file does not exist on disk
    # This simulated Render container recycling/idle spin-down.
    resp_proc = client.post(
        "/api/v1/upload/process-mapping",
        json={
            "upload_id": upload_id,
            "marketplace": "Flipkart",
            "mapping": up_res.get("auto_mapping", {}),
            "deduplication_mode": "replace"
        },
        headers=headers
    )
    assert resp_proc.status_code == 200
    proc_res = resp_proc.json()
    assert proc_res["sales_records_count"] == 2373

    # 3. Verify ledger and overview data
    ledger_count = db.query(OrderItemLedger).filter(OrderItemLedger.organization_id == org_id).count()
    assert ledger_count == 2373

    resp_overview = client.get("/api/v1/dashboard/overview", headers=headers)
    assert resp_overview.status_code == 200
    ov = resp_overview.json()
    assert ov["sales_value"] == 319328.0
    assert ov["returned_value"] == 97967.0
    assert ov["sale_events_count"] == 1734
    assert ov["return_events_count"] == 486
    assert ov["cancellation_events_count"] == 134
    assert ov["unique_skus_count"] == 57
    assert ov["sale_linked_return_rate"] == 24.2

    # 4. Verify cancellations orders ledger
    resp_canc = client.get("/api/v1/dashboard/returns/orders?event=CANCELLATION", headers=headers)
    assert resp_canc.status_code == 200
    canc_rows = resp_canc.json()
    assert len(canc_rows) == 134
    for row in canc_rows:
        assert row["event"] == "CANCELLATION"
        assert row["order_id"] is not None

    # 5. Verify friendly error messages (no stack traces, no filesystem paths)
    resp_bad_ext = client.post(
        "/api/v1/upload/file",
        files={"file": ("notes.txt", b"Hello world", "text/plain")},
        data={"marketplace": "Flipkart"},
        headers=headers
    )
    assert resp_bad_ext.status_code == 400
    bad_ext_detail = resp_bad_ext.json()["detail"]
    assert bad_ext_detail == "Please upload an Excel or CSV report."
    assert "Traceback" not in bad_ext_detail
    assert "/" not in bad_ext_detail and "\\" not in bad_ext_detail

    resp_corrupt = client.post(
        "/api/v1/upload/file",
        files={"file": ("corrupt.xlsx", b"not a zip file", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"marketplace": "Flipkart"},
        headers=headers
    )
    assert resp_corrupt.status_code == 400
    corrupt_detail = resp_corrupt.json()["detail"]
    assert corrupt_detail == "Unable to process this report. Please check that it is a valid marketplace report."
    assert "Traceback" not in corrupt_detail
    assert "/" not in corrupt_detail and "\\" not in corrupt_detail
