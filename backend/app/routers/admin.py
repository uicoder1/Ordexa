from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.database import get_db
from app.models.models import User, Organization, OrganizationMember, UploadedFile, AuditLog, OrganizationSubscription
from app.auth.auth import get_current_user, require_platform_admin

router = APIRouter(prefix="/admin", tags=["Platform Administration"])

@router.get("/overview")
def get_platform_overview(
    current_admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Returns platform-level operational KPIs for the Ordexa platform administrator.
    """
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_orgs = db.query(func.count(Organization.id)).scalar() or 0
    total_uploads = db.query(func.count(UploadedFile.id)).scalar() or 0
    total_audit_events = db.query(func.count(AuditLog.id)).scalar() or 0

    return {
        "platform_name": "Ordexa Admin Operations",
        "total_organizations": total_orgs,
        "total_users": total_users,
        "total_uploads": total_uploads,
        "total_audit_events": total_audit_events,
        "timestamp": datetime.utcnow()
    }

@router.get("/organizations")
def list_platform_organizations(
    limit: int = Query(50, le=200),
    current_admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Lists platform organizations without exposing granular product or customer records.
    """
    orgs = db.query(Organization).order_by(Organization.created_at.desc()).limit(limit).all()
    results = []
    for org in orgs:
        owner = db.query(User).filter(User.id == org.owner_id).first()
        member_count = db.query(func.count(OrganizationMember.id)).filter(
            OrganizationMember.organization_id == org.id
        ).scalar() or 0
        upload_count = db.query(func.count(UploadedFile.id)).filter(
            UploadedFile.organization_id == org.id
        ).scalar() or 0

        results.append({
            "id": org.id,
            "name": org.name,
            "owner_email": owner.email if owner else "Unknown",
            "owner_id": org.owner_id,
            "sales_channels": org.sales_channels,
            "member_count": member_count,
            "upload_count": upload_count,
            "created_at": org.created_at
        })
    return results

@router.get("/users")
def list_platform_users(
    limit: int = Query(50, le=200),
    current_admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Lists all platform registered users, their registration dates, and last login timestamps.
    """
    users = db.query(User).order_by(User.created_at.desc()).limit(limit).all()
    results = []
    for u in users:
        membership = db.query(OrganizationMember).filter(
            OrganizationMember.user_id == u.id
        ).first()
        org_name = "None"
        org_role = "None"
        if membership:
            org = db.query(Organization).filter(Organization.id == membership.organization_id).first()
            if org:
                org_name = org.name
            org_role = membership.role or "member"

        results.append({
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "organization_name": org_name,
            "organization_role": org_role,
            "is_platform_admin": bool(u.is_platform_admin),
            "created_at": u.created_at,
            "last_login_at": u.last_login_at
        })
    return results

@router.get("/uploads")
def list_platform_upload_activity(
    limit: int = Query(50, le=200),
    current_admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Platform-wide view of report upload jobs, file formats, rows processed, and processing statuses.
    """
    uploads = db.query(UploadedFile).order_by(UploadedFile.uploaded_at.desc()).limit(limit).all()
    return [
        {
            "id": up.id,
            "organization_id": up.organization_id,
            "filename": up.filename,
            "marketplace": up.marketplace,
            "file_type": up.file_type,
            "file_size": up.file_size,
            "upload_status": up.upload_status,
            "rows_processed": up.rows_processed,
            "rows_failed": up.rows_failed,
            "uploaded_at": up.uploaded_at,
            "error_message": up.error_message
        }
        for up in uploads
    ]

@router.get("/audit-logs")
def list_platform_audit_logs(
    limit: int = Query(100, le=500),
    action: Optional[str] = None,
    current_admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Lists recent audit events for security and compliance monitoring.
    """
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action.strip().upper())
    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "organization_id": l.organization_id,
            "user_id": l.user_id,
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "metadata": l.metadata_json,
            "ip_address": l.ip_address,
            "user_agent": l.user_agent,
            "created_at": l.created_at
        }
        for l in logs
    ]

@router.post("/users/{user_id}/toggle-admin")
def toggle_user_platform_admin(
    user_id: str,
    current_admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Allows a platform administrator to promote or demote platform admin status for a user.
    Prevents self-demotion to avoid lockout.
    """
    if current_admin.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change platform admin status on your own account."
        )

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    target_user.is_platform_admin = not bool(target_user.is_platform_admin)
    db.commit()

    return {
        "message": f"User '{target_user.email}' platform admin status set to {target_user.is_platform_admin}.",
        "user_id": target_user.id,
        "is_platform_admin": target_user.is_platform_admin
    }


@router.get("/users/{user_id}")
def get_platform_user_details(
    user_id: str,
    current_admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Detailed platform view of a specific user and their organization memberships.
    """
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    memberships = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == target_user.id
    ).all()

    orgs = []
    for m in memberships:
        org = db.query(Organization).filter(Organization.id == m.organization_id).first()
        if org:
            orgs.append({
                "organization_id": org.id,
                "organization_name": org.name,
                "role": m.role or "member",
                "joined_at": m.created_at
            })

    return {
        "id": target_user.id,
        "email": target_user.email,
        "name": target_user.name,
        "is_platform_admin": bool(target_user.is_platform_admin),
        "created_at": target_user.created_at,
        "last_login_at": target_user.last_login_at,
        "organizations": orgs
    }


@router.get("/organizations/{org_id}")
def get_platform_organization_details(
    org_id: str,
    current_admin: User = Depends(require_platform_admin),
    db: Session = Depends(get_db)
):
    """
    Detailed platform view of an organization, its members, upload metrics, and recent activity.
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found."
        )

    owner = db.query(User).filter(User.id == org.owner_id).first()

    from app.models.models import Product
    upload_count = db.query(func.count(UploadedFile.id)).filter(
        UploadedFile.organization_id == org.id
    ).scalar() or 0
    product_count = db.query(func.count(Product.id)).filter(
        Product.organization_id == org.id
    ).scalar() or 0

    memberships = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org.id
    ).all()
    members = []
    for m in memberships:
        u = db.query(User).filter(User.id == m.user_id).first()
        if u:
            members.append({
                "user_id": u.id,
                "name": u.name,
                "email": u.email,
                "role": m.role or "member",
                "joined_at": m.created_at
            })

    recent_uploads = db.query(UploadedFile).filter(
        UploadedFile.organization_id == org.id
    ).order_by(UploadedFile.uploaded_at.desc()).limit(10).all()

    recent_logs = db.query(AuditLog).filter(
        AuditLog.organization_id == org.id
    ).order_by(AuditLog.created_at.desc()).limit(10).all()

    return {
        "id": org.id,
        "name": org.name,
        "owner_id": org.owner_id,
        "owner_email": owner.email if owner else "Unknown",
        "sales_channels": org.sales_channels,
        "created_at": org.created_at,
        "member_count": len(members),
        "upload_count": upload_count,
        "product_count": product_count,
        "members": members,
        "recent_uploads": [
            {
                "id": up.id,
                "filename": up.filename,
                "marketplace": up.marketplace,
                "upload_status": up.upload_status,
                "rows_processed": up.rows_processed,
                "uploaded_at": up.uploaded_at
            }
            for up in recent_uploads
        ],
        "recent_activity": [
            {
                "id": l.id,
                "action": l.action,
                "resource_type": l.resource_type,
                "created_at": l.created_at
            }
            for l in recent_logs
        ]
    }
