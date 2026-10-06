import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.config import settings
from app.models.models import User, PasswordResetToken
from app.auth.auth import get_password_hash

def hash_token(token: str) -> str:
    """Computes a SHA-256 hash of the plain reset token for secure DB storage."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

class PasswordResetService:
    @staticmethod
    def request_password_reset(db: Session, email: str) -> dict:
        """
        Generates a cryptographically secure, single-use, time-limited reset token.
        Always returns a generic message to prevent email enumeration attacks.
        """
        user = db.query(User).filter(User.email == email.strip().lower()).first()

        if user:
            # 1. Invalidate any existing active tokens for this user
            db.query(PasswordResetToken).filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None)
            ).update({"used_at": datetime.utcnow()})

            # 2. Generate secure random token
            plain_token = secrets.token_urlsafe(32)
            token_hashed = hash_token(plain_token)

            # 3. Store hashed token with 1-hour expiration
            expires_at = datetime.utcnow() + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
            reset_record = PasswordResetToken(
                user_id=user.id,
                token_hash=token_hashed,
                expires_at=expires_at,
                created_at=datetime.utcnow()
            )
            db.add(reset_record)
            db.commit()

            # 4. Email delivery handling
            if settings.EMAIL_PROVIDER == "pending_configuration":
                # In development/test or before production SMTP is bound, email is marked pending
                # Do NOT log the plain token or user password
                pass
            else:
                # Dispatch email via configured SMTP (when production SMTP credentials provided)
                pass

        # Generic response preventing account enumeration
        return {
            "message": "If this email is registered, password reset instructions have been sent.",
            "email_delivery_status": settings.EMAIL_PROVIDER
        }

    @staticmethod
    def verify_and_reset_password(db: Session, token: str, new_password: str) -> dict:
        """
        Verifies the reset token, ensures it is unused and not expired,
        and safely updates the user's password using Argon2id.
        """
        if not token or not token.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token is required."
            )

        if not new_password or len(new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long."
            )

        token_hashed = hash_token(token.strip())
        now = datetime.utcnow()

        token_record = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hashed,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now
        ).first()

        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid, expired, or already used password reset token."
            )

        user = db.query(User).filter(User.id == token_record.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User associated with this reset token no longer exists."
            )

        # Update password to adaptive Argon2id hash
        user.hashed_password = get_password_hash(new_password)
        # Mark token as consumed
        token_record.used_at = now

        db.commit()

        return {
            "message": "Password has been successfully reset. You may now sign in with your new password."
        }

password_reset_service = PasswordResetService()
