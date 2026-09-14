"""The synthetic principal used when authentication is disabled.

`AUTH_DISABLED=true` still has to produce valid foreign keys (an AI system needs a real
`owner_id`) and a truthful audit trail. Rather than inventing an in-memory object that
would break both, the system principal is a real, reserved user row that:

* has the fixed address `system@ai-gov.internal` and the admin role,
* is flagged `is_system`, which makes it unusable for login on any code path,
* carries an unusable password hash, so even a leaked token cannot be exchanged for it.

Audit entries written under it are labelled `system` with `actor_type=system`, so an
operator can always tell an unauthenticated deployment's actions from a real user's.
"""

from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User

logger = get_logger(__name__)

#: `system@internal` has no TLD, which `EmailStr` rejects. `.internal` is the TLD
#: reserved for private networks, so this keeps the intent and stays a valid address.
SYSTEM_USER_EMAIL = "system@ai-gov.internal"
SYSTEM_USER_NAME = "System (authentication disabled)"
SYSTEM_ACTOR_LABEL = "system"


def get_system_user(db: Session) -> User:
    """Fetch the reserved system principal, creating it on first use."""
    user = db.execute(select(User).where(User.email == SYSTEM_USER_EMAIL)).scalar_one_or_none()
    if user is not None:
        return user

    user = User(
        email=SYSTEM_USER_EMAIL,
        full_name=SYSTEM_USER_NAME,
        role=UserRole.ADMIN,
        # Random and never disclosed: the account is unusable for login regardless,
        # but an unusable hash means a misconfiguration cannot turn into a login.
        hashed_password=hash_password(secrets.token_urlsafe(64)),
        is_active=True,
        is_system=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        # Another worker created it between the SELECT and the INSERT.
        db.rollback()
        return db.execute(select(User).where(User.email == SYSTEM_USER_EMAIL)).scalar_one()
    logger.info("system_principal_created", user_id=str(user.id))
    return user


def is_system_principal(user: User | None) -> bool:
    return bool(user is not None and user.is_system)
