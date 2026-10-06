import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, List, Callable
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from jwt import encode, decode, PyJWTError
from sqlalchemy.orm import Session
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

from app.config import settings
from app.database import get_db
from app.models.models import User, OrganizationMember, Organization

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

# Initialize Argon2id password hasher with adaptive work factor and unique per-password salt
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16
)

def get_password_hash(password: str) -> str:
    """
    Computes an Argon2id adaptive hash with a unique random salt per password.
    Never stores or logs plaintext passwords.
    """
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against an Argon2id hash.
    Transparently supports legacy development HMAC-SHA256 hashes for seamless migration.
    """
    if not hashed_password or not plain_password:
        return False

    # 1. Check if hash is Argon2 format ($argon2id$, $argon2i$, $argon2d$)
    if hashed_password.startswith("$argon2"):
        try:
            return ph.verify(hashed_password, plain_password)
        except (VerifyMismatchError, InvalidHashError):
            return False
        except Exception:
            return False

    # 2. Backward compatibility fallback for legacy single-round HMAC-SHA256 development hashes
    legacy_expected = hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        plain_password.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(legacy_expected, hashed_password)

def needs_rehash(hashed_password: str) -> bool:
    """
    Returns True if the password hash is legacy HMAC-SHA256 or needs an Argon2 parameter upgrade.
    """
    if not hashed_password or not hashed_password.startswith("$argon2"):
        return True
    try:
        return ph.check_needs_rehash(hashed_password)
    except Exception:
        return True

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except PyJWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_organization(
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Organization:
    """
    Multi-tenant security isolation dependency.
    Validates that the user has authorization to access the target organization.
    """
    if x_organization_id:
        membership = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == x_organization_id,
            OrganizationMember.user_id == current_user.id
        ).first()
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to requested organization"
            )
        org = db.query(Organization).filter(Organization.id == x_organization_id).first()
        if org:
            return org

    # Fallback to user's first available organization
    membership = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == current_user.id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No organization found for current user. Please create or join a business."
        )

    org = db.query(Organization).filter(Organization.id == membership.organization_id).first()
    return org

def get_current_membership(
    current_org: Organization = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> OrganizationMember:
    """
    Returns the OrganizationMember record for the current user in the active organization.
    """
    membership = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == current_org.id,
        OrganizationMember.user_id == current_user.id
    ).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this organization."
        )
    return membership

def require_org_role(*allowed_roles: str) -> Callable:
    """
    RBAC dependency factory.
    Enforces that the current user has one of the allowed roles (e.g. 'owner', 'admin') in the active organization.
    """
    normalized_allowed = [r.lower() for r in allowed_roles]

    def role_checker(membership: OrganizationMember = Depends(get_current_membership)) -> OrganizationMember:
        user_role = (membership.role or "member").lower()
        if user_role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role: {', '.join(allowed_roles)}. Your role: {membership.role}."
            )
        return membership

    return role_checker

def require_platform_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Platform administration security dependency.
    Restricts access strictly to global Ordexa platform administrators.
    """
    if not getattr(current_user, "is_platform_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator privileges required."
        )
    return current_user
