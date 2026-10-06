"""
Ordexa User Password Reset Script
=================================
Safely resets the password for an existing user account using Argon2id hashing.

Safety Guarantees:
- Matches user strictly by normalized email address.
- Updates ONLY the `hashed_password` field on the User record.
- Preserves `is_platform_admin` (strictly unchanged).
- Preserves name, email, workspace memberships, and all multi-tenant data.
- Securely prompts via Python `getpass` with confirmation matching.
- Plaintext password is never echoed, logged, or written to disk.
- Generates an adaptive Argon2id hash using app.auth.auth.get_password_hash.
"""

import os
import sys
import getpass
import argparse
from datetime import datetime
from typing import Dict, Any

# Ensure backend root is on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.auth.auth import get_password_hash
from app.database import SessionLocal
from app.models.models import User, PasswordResetToken


def reset_user_password(
    db,
    email: str,
    new_password: str
) -> Dict[str, Any]:
    """
    Finds exactly one user by email and updates ONLY their hashed_password using Argon2id.
    Guarantees all other attributes (is_platform_admin, memberships, etc.) remain intact.
    """
    email_clean = email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise ValueError("A valid email address is required.")

    if not new_password or len(new_password) < 8:
        raise ValueError("Password must be at least 8 characters long.")

    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        raise ValueError(f"User with email '{email_clean}' does not exist in the database.")

    # Record prior state to verify preservation
    prior_is_platform_admin = bool(user.is_platform_admin)

    # Compute Argon2id hash using application's standard security utility
    new_hash = get_password_hash(new_password)
    if not new_hash.startswith("$argon2id$"):
        raise RuntimeError("Hash generation failed to produce an Argon2id hash.")

    # Update ONLY hashed_password
    user.hashed_password = new_hash

    # Invalidate any unused legacy password reset tokens for this user
    now = datetime.utcnow()
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None)
    ).update({"used_at": now})

    db.commit()
    db.refresh(user)

    # Verification assertion
    if bool(user.is_platform_admin) != prior_is_platform_admin:
        db.rollback()
        raise RuntimeError("Integrity violation: is_platform_admin was unexpectedly mutated.")

    return {
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "is_platform_admin": user.is_platform_admin,
        "hash_format": "Argon2id"
    }


def main():
    parser = argparse.ArgumentParser(
        description="Reset an existing Ordexa user's password using Argon2id hashing."
    )
    parser.add_argument(
        "--email",
        default="anshugupta9124@gmail.com",
        help="Email address of the account to reset (default: anshugupta9124@gmail.com)."
    )
    parser.add_argument(
        "--password",
        default=os.getenv("NEW_USER_PASSWORD"),
        help="Optional password parameter (if not provided, getpass interactive prompt is used)."
    )

    args = parser.parse_args()
    email = args.email.strip().lower()

    password = args.password
    if not password:
        print(f"\nResetting password for: {email}")
        password = getpass.getpass("Enter new password (min 8 chars): ")
        password_confirm = getpass.getpass("Confirm new password: ")

        if password != password_confirm:
            print("\n[ERROR] Passwords do not match. Aborting.\n", file=sys.stderr)
            sys.exit(1)

        if len(password) < 8:
            print("\n[ERROR] Password must be at least 8 characters long.\n", file=sys.stderr)
            sys.exit(1)

    db = SessionLocal()
    try:
        res = reset_user_password(db=db, email=email, new_password=password)
        print("\n=======================================================")
        print(" ORDEXA PASSWORD RESET: SUCCESSFUL")
        print("=======================================================")
        print(f" User ID:            {res['user_id']}")
        print(f" Email:              {res['email']}")
        print(f" Name:               {res['name']}")
        print(f" Is Platform Admin:  {res['is_platform_admin']}")
        print(f" Hashing Algorithm:  {res['hash_format']} (Argon2id)")
        print(" Status:             Password updated. Existing permissions preserved.")
        print("=======================================================\n")
    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Password reset failed: {e}\n", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
