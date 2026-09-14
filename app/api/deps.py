"""Shared FastAPI dependencies: DB session, authentication, and RBAC guards.

Authentication is optional by configuration. Every dependency here routes through
:func:`resolve_principal`, which returns either the JWT-authenticated user or — when
`AUTH_DISABLED` is set — the reserved system principal with the admin role. Endpoints
therefore never branch on the mode themselves; they declare the access level they need
and the dependency enforces it.

Role matrix:

===========================  =====  ============  ======
Action                       admin  risk_officer  viewer
===========================  =====  ============  ======
Manage users and policies    yes    no            no
Create / edit AI systems     yes    yes           no
Trigger classification       yes    yes           no
Run policy checks            yes    yes           no
Generate evidence packages   yes    yes           no
View everything              yes    yes           yes
View audit logs              yes    no            no
===========================  =====  ============  ======
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import set_actor
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.principal import get_system_user
from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User

# auto_error=False so a missing header reaches our own handler and produces the
# standard error envelope rather than FastAPI's default shape.
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="JWT access token. Not required when the server runs with AUTH_DISABLED.",
)

DbSession = Annotated[Session, Depends(get_db)]
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def _authenticate_token(db: Session, token: str) -> User:
    payload = decode_token(token, expected_type="access")
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except ValueError as exc:
        raise AuthenticationError("Malformed token subject.") from exc

    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise AuthenticationError("Token does not match an active user.")
    if not user.is_active:
        raise AuthenticationError("This account is disabled.")
    if user.is_system:
        # The reserved principal is never reachable by token.
        raise AuthenticationError("This account cannot be used for API access.")
    return user


def resolve_principal(db: Session, credentials: HTTPAuthorizationCredentials | None) -> User:
    """The single place that decides who is making a request.

    With authentication disabled the request is attributed to the system principal, so
    downstream code — ownership, audit entries — still has a real user to point at.
    """
    if settings.AUTH_DISABLED:
        user = get_system_user(db)
    else:
        if credentials is None or not credentials.credentials:
            raise AuthenticationError("Authentication required.")
        user = _authenticate_token(db, credentials.credentials)
    set_actor(str(user.id), user.email)
    return user


def get_current_user(db: DbSession, credentials: BearerCredentials = None) -> User:
    """The authenticated user, or the system principal when auth is disabled."""
    return resolve_principal(db, credentials)


def get_current_user_optional(db: DbSession, credentials: BearerCredentials = None) -> User | None:
    """Identify the caller where possible, but never reject them.

    Returns the system principal when auth is disabled, the authenticated user when a
    valid token is presented, and ``None`` when a token is absent or invalid. Use it for
    endpoints that are readable anonymously but should still attribute an actor when one
    is known — never as a substitute for :func:`get_current_user` on a protected route.
    """
    if settings.AUTH_DISABLED:
        return resolve_principal(db, credentials)
    if credentials is None or not credentials.credentials:
        return None
    try:
        user = _authenticate_token(db, credentials.credentials)
    except AuthenticationError:
        return None
    set_actor(str(user.id), user.email)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """Guard requiring one of ``roles``.

    With AUTH_DISABLED the principal holds the admin role, so every guard passes. That
    is the documented meaning of the mode: the network is the access control.
    """
    allowed = set(roles)

    def _guard(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise PermissionDeniedError(
                f"This action requires one of: {', '.join(sorted(r.value for r in allowed))}. "
                f"Your role is '{user.role}'."
            )
        return user

    _guard.__name__ = f"require_{'_or_'.join(sorted(r.value for r in allowed))}"
    return _guard


#: Admin only: user management, policy management, audit log access.
require_admin = require_roles(UserRole.ADMIN)
#: Admin or risk officer: everything that mutates inventory or runs an assessment.
require_risk_officer = require_roles(UserRole.ADMIN, UserRole.RISK_OFFICER)
#: Any authenticated role, including viewer. Read access.
require_viewer = require_roles(UserRole.ADMIN, UserRole.RISK_OFFICER, UserRole.VIEWER)

#: Previous name for `require_risk_officer`.
require_writer = require_risk_officer

AdminUser = Annotated[User, Depends(require_admin)]
RiskOfficerUser = Annotated[User, Depends(require_risk_officer)]
#: Previous name for `RiskOfficerUser`.
WriterUser = RiskOfficerUser


def get_request_id_header(request: Request) -> str:
    return getattr(request.state, "request_id", "")
