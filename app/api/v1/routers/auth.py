"""Authentication: login, refresh, current user, admin user management."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.api.envelope import EnvelopeRoute
from app.api.rate_limit import limiter, login_limit
from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.enums import AuditAction
from app.schemas.auth import (
    AuthMode,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.schemas.common import ErrorResponse, Page
from app.services.audit import record_audit
from app.services.user import UserService

router = APIRouter(prefix="/auth", tags=["auth"], route_class=EnvelopeRoute)

ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
}


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange credentials for a JWT pair",
    responses={**ERRORS, 429: {"model": ErrorResponse}},
)
@limiter.limit(login_limit)
def login(
    request: Request, response: Response, payload: LoginRequest, db: DbSession
) -> TokenResponse:
    """Issue an access/refresh pair.

    Rate limited per client to blunt credential stuffing. Failed attempts are written to
    the audit trail and committed before the error propagates, so a rolled-back request
    still leaves the evidence behind.
    """
    try:
        user = UserService(db).authenticate(payload.email, payload.password)
    except AuthenticationError:
        record_audit(
            db,
            resource_type="user",
            action=AuditAction.LOGIN_FAILED,
            context={"email": payload.email},
        )
        db.commit()
        raise
    return TokenResponse(
        access_token=create_access_token(str(user.id), role=str(user.role), email=user.email),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate an access token",
    responses={**ERRORS, 429: {"model": ErrorResponse}},
)
@limiter.limit(login_limit)
def refresh(
    request: Request, response: Response, payload: RefreshRequest, db: DbSession
) -> TokenResponse:
    claims = decode_token(payload.refresh_token, expected_type="refresh")
    user = UserService(db).get(uuid.UUID(str(claims["sub"])))
    return TokenResponse(
        access_token=create_access_token(str(user.id), role=str(user.role), email=user.email),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserRead, summary="Current principal")
def me(current_user: CurrentUser) -> UserRead:
    """The authenticated user, or the system principal when AUTH_DISABLED is set.

    `is_system` tells a client which mode the server is running in.
    """
    return UserRead.model_validate(current_user)


@router.get(
    "/mode",
    response_model=AuthMode,
    summary="Report the server's authentication mode",
)
def auth_mode() -> AuthMode:
    """Unauthenticated: lets a client decide whether to show a login screen."""
    return AuthMode(
        auth_enabled=settings.auth_enabled,
        auth_disabled=settings.AUTH_DISABLED,
        access_token_expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token_expires_in=settings.refresh_token_expire_minutes * 60,
    )


@router.get(
    "/users",
    response_model=Page[UserRead],
    summary="List users (admin only)",
    responses=ERRORS,
)
def list_users(
    db: DbSession,
    _: AdminUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> Page[UserRead]:
    users, total = UserService(db).list_users(offset=(page - 1) * page_size, limit=page_size)
    return Page[UserRead](
        items=[UserRead.model_validate(u) for u in users],
        meta={
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        },
    )


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user (admin only)",
    responses=ERRORS,
)
def create_user(payload: UserCreate, db: DbSession, admin: AdminUser) -> UserRead:
    return UserRead.model_validate(UserService(db).create(payload, actor=admin))


@router.patch(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Update a user (admin only)",
    responses=ERRORS,
)
def update_user(
    user_id: uuid.UUID, payload: UserUpdate, db: DbSession, admin: AdminUser
) -> UserRead:
    return UserRead.model_validate(UserService(db).update(user_id, payload, actor=admin))
