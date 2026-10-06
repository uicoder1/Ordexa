import hmac
import hashlib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.config import settings
from app.models.models import User, Organization, OrganizationMember, AuditLog
from app.auth.auth import get_password_hash, verify_password, needs_rehash

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

def test_password_hasher_unit():
    raw_pw = "SuperSecurePass99!"
    hashed = get_password_hash(raw_pw)

    # Must be Argon2id
    assert hashed.startswith("$argon2id$")
    assert verify_password(raw_pw, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert needs_rehash(hashed) is False

def test_legacy_hmac_verification_and_rehash_detection():
    secret = settings.SECRET_KEY.encode('utf-8')
    plain = "OldLegacyDevPass123!"
    legacy_hash = hmac.new(secret, plain.encode('utf-8'), hashlib.sha256).hexdigest()

    assert len(legacy_hash) == 64
    assert verify_password(plain, legacy_hash) is True
    assert verify_password("Incorrect", legacy_hash) is False
    assert needs_rehash(legacy_hash) is True

def test_registration_and_argon2_storage(isolated_db):
    db, client = isolated_db

    resp = client.post("/api/v1/auth/signup", json={
        "email": "newtenant@ordexa.com",
        "password": "SecurePassword123!",
        "name": "Jane Founder",
        "company_name": "Jane Enterprises"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "newtenant@ordexa.com"

    # Verify database record
    user_db = db.query(User).filter(User.email == "newtenant@ordexa.com").first()
    assert user_db is not None
    assert user_db.hashed_password.startswith("$argon2id$")
    assert user_db.hashed_password != "SecurePassword123!"

    # Verify audit log was created without leaking password
    audit = db.query(AuditLog).filter(AuditLog.action == "USER_REGISTERED").first()
    assert audit is not None
    assert "password" not in audit.metadata_json.lower()
    assert "securepassword" not in audit.metadata_json.lower()

def test_login_success_and_failure(isolated_db):
    db, client = isolated_db

    # Register
    client.post("/api/v1/auth/signup", json={
        "email": "seller_login@ordexa.com",
        "password": "LoginSecret456!",
        "name": "Alex Seller"
    })

    # Incorrect password
    bad_resp = client.post("/api/v1/auth/login", json={
        "email": "seller_login@ordexa.com",
        "password": "WrongPassword!"
    })
    assert bad_resp.status_code == 401

    # Check FAILED_LOGIN audit log
    failed_audit = db.query(AuditLog).filter(AuditLog.action == "FAILED_LOGIN").first()
    assert failed_audit is not None
    assert "password" not in failed_audit.metadata_json.lower()

    # Correct password
    good_resp = client.post("/api/v1/auth/login", json={
        "email": "seller_login@ordexa.com",
        "password": "LoginSecret456!"
    })
    assert good_resp.status_code == 200
    assert "access_token" in good_resp.json()

    # Check USER_LOGIN audit log
    login_audit = db.query(AuditLog).filter(AuditLog.action == "USER_LOGIN").first()
    assert login_audit is not None

def test_transparent_password_rehash_migration(isolated_db):
    """
    Existing development accounts with legacy HMAC-SHA256 hashes must
    authenticate successfully and be transparently rehashed to Argon2id on first login.
    """
    db, client = isolated_db

    # Simulate legacy development user with HMAC-SHA256
    legacy_plain = "LegacyDevPassword123!"
    legacy_hash = hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        legacy_plain.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    user = User(
        id="legacy-user-1",
        email="legacy_user@ordexa.com",
        hashed_password=legacy_hash,
        name="Legacy Dev User"
    )
    db.add(user)
    org = Organization(id="legacy-org-1", name="Legacy Org", owner_id=user.id)
    db.add(org)
    mem = OrganizationMember(organization_id=org.id, user_id=user.id, role="owner")
    db.add(mem)
    db.commit()

    # Confirm initial state is 64-char hex legacy hash
    user_before = db.query(User).filter(User.id == "legacy-user-1").first()
    assert user_before.hashed_password == legacy_hash
    assert not user_before.hashed_password.startswith("$argon2id$")

    # Login with existing password
    resp = client.post("/api/v1/auth/login", json={
        "email": "legacy_user@ordexa.com",
        "password": legacy_plain
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()

    # Check database: hash must be transparently upgraded to Argon2id!
    db.refresh(user_before)
    assert user_before.hashed_password.startswith("$argon2id$")
    assert user_before.hashed_password != legacy_hash

    # Next login still succeeds with newly stored Argon2id hash
    resp2 = client.post("/api/v1/auth/login", json={
        "email": "legacy_user@ordexa.com",
        "password": legacy_plain
    })
    assert resp2.status_code == 200
