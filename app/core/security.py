"""Password hashing and JWT issuance/verification."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import AuthenticationError

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh"]


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd_context.verify(plain, hashed)
    except ValueError:
        return False


def _create_token(subject: str, token_type: TokenType, expires_minutes: int, **claims: Any) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
        "jti": str(uuid.uuid4()),
        **claims,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, *, role: str, email: str) -> str:
    return _create_token(
        subject,
        "access",
        settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        role=role,
        email=email,
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(subject, "refresh", settings.refresh_token_expire_minutes)


def decode_token(token: str, *, expected_type: TokenType = "access") -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:  # expired, bad signature, malformed
        raise AuthenticationError("Invalid or expired token.") from exc
    if payload.get("type") != expected_type:
        raise AuthenticationError(f"Expected a {expected_type} token.")
    if not payload.get("sub"):
        raise AuthenticationError("Token is missing a subject.")
    return payload
