import json
from datetime import datetime
from typing import Optional, Any, Dict
from fastapi import Request
from sqlalchemy.orm import Session
from app.models.models import AuditLog

# Deny-list of sensitive keys that must NEVER be written to audit logs
SENSITIVE_KEYS = {
    "password",
    "plain_password",
    "hashed_password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "secret_key",
    "api_key",
    "authorization",
    "token_hash",
    "raw_contents",
    "contents",
}

class AuditService:
    @staticmethod
    def sanitize_metadata(data: Optional[Dict[str, Any]]) -> Optional[str]:
        if not data:
            return None
        
        sanitized: Dict[str, Any] = {}
        for k, v in data.items():
            key_lower = str(k).lower().strip()
            if any(s in key_lower for s in SENSITIVE_KEYS):
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, (str, int, float, bool)) or v is None:
                sanitized[k] = v
            elif isinstance(v, list):
                # Ensure list items don't leak secrets
                sanitized[k] = [
                    item if isinstance(item, (int, float, bool)) else str(item)[:100]
                    for item in v[:50]
                ]
            elif isinstance(v, dict):
                sanitized[k] = {
                    dk: "[REDACTED]" if any(s in str(dk).lower() for s in SENSITIVE_KEYS) else str(dv)[:100]
                    for dk, dv in list(v.items())[:20]
                }
            else:
                sanitized[k] = str(v)[:100]

        return json.dumps(sanitized)

    @staticmethod
    def log_event(
        db: Session,
        action: str,
        organization_id: Optional[str] = None,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """
        Records a business/security audit event without capturing secrets or personal passwords.
        """
        try:
            client_ip = ip_address
            client_ua = user_agent

            if request:
                if not client_ip and request.client:
                    client_ip = request.client.host
                if not client_ua:
                    client_ua = request.headers.get("user-agent")

            sanitized_meta = AuditService.sanitize_metadata(metadata)

            audit_entry = AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata_json=sanitized_meta,
                ip_address=client_ip,
                user_agent=client_ua,
                created_at=datetime.utcnow()
            )
            db.add(audit_entry)
            db.commit()
            return audit_entry
        except Exception:
            # Audit logging failure should not crash core application transactions
            db.rollback()
            return None

audit_service = AuditService()
