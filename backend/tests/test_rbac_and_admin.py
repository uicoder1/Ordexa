import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.models import (
    User, Organization, OrganizationMember, UploadedFile
)
from app.auth.auth import create_access_token

@pytest.fixture
def isolated_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield db, TestClient(app)
    app.dependency_overrides.clear()
    db.close()

def test_rbac_member_cannot_perform_owner_actions(isolated_db):
    db, client = isolated_db

    # 1. Create Organization with an Owner and a Member
    owner = User(id="u-owner", email="owner@shop.com", hashed_password="pw", name="Owner")
    member = User(id="u-member", email="member@shop.com", hashed_password="pw", name="Member")
    db.add_all([owner, member])
    
    org = Organization(id="org-rbac", name="RBAC Shop", owner_id=owner.id)
    db.add(org)

    mem_owner = OrganizationMember(organization_id=org.id, user_id=owner.id, role="owner")
    mem_member = OrganizationMember(organization_id=org.id, user_id=member.id, role="member")
    db.add_all([mem_owner, mem_member])

    upload = UploadedFile(id="up-rbac", organization_id=org.id, filename="data.xlsx", storage_path="p.xlsx")
    db.add(upload)
    db.commit()

    token_member = create_access_token(data={"sub": member.id})
    headers_member = {"Authorization": f"Bearer {token_member}", "X-Organization-ID": org.id}

    token_owner = create_access_token(data={"sub": owner.id})
    headers_owner = {"Authorization": f"Bearer {token_owner}", "X-Organization-ID": org.id}

    # 2. Member tries to update organization configuration (Owner-only) -> 403 Forbidden
    res_conf = client.put("/api/v1/organizations/config", json={"critical_risk_margin_threshold": 12.0}, headers=headers_member)
    assert res_conf.status_code == 403
    assert "Insufficient organization permissions" in res_conf.json()["detail"] or "Operation not permitted" in res_conf.json()["detail"]

    # 3. Member tries to delete an import record (Owner-only) -> 403 Forbidden
    res_del = client.delete(f"/api/v1/imports/{upload.id}", headers=headers_member)
    assert res_del.status_code == 403

    # 4. Member tries bulk cost upload (Admin/Owner only) -> 403 Forbidden
    res_cost = client.post("/api/v1/products/bulk-cost-upload", files={"file": ("c.csv", b"SKU,Purchase Cost\nA,10", "text/csv")}, headers=headers_member)
    assert res_cost.status_code == 403

    # 5. Owner CAN update organization configuration
    res_conf_owner = client.put("/api/v1/organizations/config", json={"critical_risk_margin_threshold": 12.0}, headers=headers_owner)
    assert res_conf_owner.status_code == 200

def test_platform_admin_security_enforcement(isolated_db):
    db, client = isolated_db

    # Standard User
    regular_user = User(id="u-regular", email="regular@example.com", hashed_password="pw", name="Regular", is_platform_admin=False)
    # Platform Admin User
    admin_user = User(id="u-admin", email="admin@ordexa.com", hashed_password="pw", name="Admin", is_platform_admin=True)
    db.add_all([regular_user, admin_user])
    db.commit()

    token_regular = create_access_token(data={"sub": regular_user.id})
    headers_regular = {"Authorization": f"Bearer {token_regular}"}

    token_admin = create_access_token(data={"sub": admin_user.id})
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    # 1. Regular user accessing /admin endpoints -> 403 Forbidden
    assert client.get("/api/v1/admin/overview", headers=headers_regular).status_code == 403
    assert client.get("/api/v1/admin/organizations", headers=headers_regular).status_code == 403
    assert client.get("/api/v1/admin/users", headers=headers_regular).status_code == 403
    assert client.get("/api/v1/admin/uploads", headers=headers_regular).status_code == 403
    assert client.get("/api/v1/admin/audit-logs", headers=headers_regular).status_code == 403

    # 2. Platform Admin accessing /admin endpoints -> 200 OK
    resp_overview = client.get("/api/v1/admin/overview", headers=headers_admin)
    assert resp_overview.status_code == 200
    data = resp_overview.json()
    assert "total_users" in data
    assert "total_organizations" in data

    resp_users = client.get("/api/v1/admin/users", headers=headers_admin)
    assert resp_users.status_code == 200
    assert len(resp_users.json()) == 2

    # 3. User details endpoint
    assert client.get(f"/api/v1/admin/users/{regular_user.id}", headers=headers_regular).status_code == 403
    resp_detail = client.get(f"/api/v1/admin/users/{regular_user.id}", headers=headers_admin)
    assert resp_detail.status_code == 200
    detail_data = resp_detail.json()
    assert detail_data["email"] == "regular@example.com"
    assert "hashed_password" not in detail_data
    assert "password" not in detail_data

    # 4. Verify auth/me returns is_platform_admin correctly
    me_reg = client.get("/api/v1/auth/me", headers=headers_regular)
    assert me_reg.status_code == 200
    assert me_reg.json()["is_platform_admin"] is False

    me_admin = client.get("/api/v1/auth/me", headers=headers_admin)
    assert me_admin.status_code == 200
    assert me_admin.json()["is_platform_admin"] is True


def test_reset_user_password_preserves_platform_admin(isolated_db):
    from scripts.reset_user_password import reset_user_password

    db, client = isolated_db
    target_email = "anshugupta9124@gmail.com"

    # Create admin user
    admin_user = User(
        id="u-admin-pwd-test",
        email=target_email,
        name="Anshu Gupta",
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$oldhash$salt",
        is_platform_admin=True
    )
    db.add(admin_user)
    db.commit()

    # Reset password
    new_password = "BrandNewSuperSecurePassword999!"
    res = reset_user_password(db, email=target_email, new_password=new_password)

    assert res["user_id"] == "u-admin-pwd-test"
    assert res["is_platform_admin"] is True
    assert res["email"] == target_email

    # Verify user record in database
    db_user = db.query(User).filter(User.email == target_email).first()
    assert db_user.is_platform_admin is True
    assert db_user.hashed_password.startswith("$argon2id$")
    assert new_password not in db_user.hashed_password
    assert db_user.name == "Anshu Gupta"

    # Authenticate via /api/v1/auth/login using new password
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": target_email, "password": new_password}
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert login_data["user"]["is_platform_admin"] is True
    assert login_data["user"]["email"] == target_email
    assert "password" not in login_data["user"]
    assert "hashed_password" not in login_data["user"]
