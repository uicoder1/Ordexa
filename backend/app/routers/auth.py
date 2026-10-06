from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import User, Organization, OrganizationMember, OrganizationSubscription
from app.schemas.schemas import UserCreate, UserResponse, LoginRequest, Token, PasswordResetRequest, PasswordResetConfirm
from app.auth.auth import (
    verify_password,
    get_password_hash,
    needs_rehash,
    create_access_token,
    get_current_user
)
from app.services.audit import audit_service
from app.services.password_reset import password_reset_service

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", response_model=Token)
def signup(user_in: UserCreate, request: Request, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_in.email.strip().lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists."
        )

    # 1. Create User with adaptive Argon2id hashing
    user = User(
        email=user_in.email.strip().lower(),
        hashed_password=get_password_hash(user_in.password),
        name=user_in.name.strip(),
        last_login_at=datetime.utcnow()
    )
    db.add(user)
    db.flush()

    # 2. Create Company / Organization for User
    if user_in.company_name and user_in.company_name.strip():
        org_name = user_in.company_name.strip()
    elif user_in.name and user_in.name.strip():
        org_name = f"{user_in.name.strip()}'s Workspace"
    else:
        org_name = "My Workspace"

    org = Organization(
        name=org_name,
        owner_id=user.id,
        sales_channels="Amazon,Flipkart,Shopify"
    )
    db.add(org)
    db.flush()

    # 3. Add Member as Owner
    member = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role="owner"
    )
    db.add(member)

    # 4. Add Subscription
    sub = OrganizationSubscription(
        organization_id=org.id,
        plan="starter",
        status="active"
    )
    db.add(sub)
    db.commit()
    db.refresh(user)

    # 5. Audit Logging (strictly no passwords or secrets)
    audit_service.log_event(
        db=db,
        action="USER_REGISTERED",
        organization_id=org.id,
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        metadata={"email": user.email, "company": org.name},
        request=request
    )

    access_token = create_access_token(data={"sub": user.id})
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user),
        active_organization_id=org.id
    )

@router.post("/login", response_model=Token)
def login(login_in: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email_clean = login_in.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()

    if not user or not verify_password(login_in.password, user.hashed_password):
        audit_service.log_event(
            db=db,
            action="FAILED_LOGIN",
            user_id=user.id if user else None,
            organization_id=None,
            resource_type="auth",
            metadata={"attempted_email": email_clean},
            request=request
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    # Find active org
    membership = db.query(OrganizationMember).filter(OrganizationMember.user_id == user.id).first()
    active_org_id = membership.organization_id if membership else None

    # Transparent password migration: rehash old HMAC-SHA256 to Argon2id on successful auth
    if needs_rehash(user.hashed_password):
        user.hashed_password = get_password_hash(login_in.password)

    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    # Audit logging for successful login
    audit_service.log_event(
        db=db,
        action="USER_LOGIN",
        organization_id=active_org_id,
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        metadata={"email": user.email},
        request=request
    )

    access_token = create_access_token(data={"sub": user.id})
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user),
        active_organization_id=active_org_id
    )

@router.post("/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    membership = db.query(OrganizationMember).filter(OrganizationMember.user_id == current_user.id).first()
    org_id = membership.organization_id if membership else None

    audit_service.log_event(
        db=db,
        action="USER_LOGOUT",
        organization_id=org_id,
        user_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        metadata={"email": current_user.email},
        request=request
    )
    return {"message": "Successfully signed out."}

@router.post("/forgot-password")
def forgot_password(req: PasswordResetRequest, db: Session = Depends(get_db)):
    """
    Initiates a secure password reset request without disclosing email existence.
    """
    return password_reset_service.request_password_reset(db, req.email)

@router.post("/reset-password")
def reset_password(req: PasswordResetConfirm, db: Session = Depends(get_db)):
    """
    Confirms password reset using single-use cryptographically verified token.
    """
    return password_reset_service.verify_and_reset_password(db, req.token, req.new_password)

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
