from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: EmailStr = Field(examples=["admin@aigov.example.com"])
    password: str = Field(min_length=8, examples=["ChangeMe123!"])


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(examples=[28800], description="Access token lifetime in seconds")


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.VIEWER


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserRead(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    is_system: bool = Field(
        default=False,
        description="True for the synthetic principal used when AUTH_DISABLED is set.",
    )
    created_at: datetime


class AuthMode(BaseModel):
    """Whether this deployment requires credentials."""

    auth_enabled: bool = Field(examples=[True])
    auth_disabled: bool = Field(examples=[False])
    access_token_expires_in: int = Field(examples=[1800], description="Seconds.")
    refresh_token_expires_in: int = Field(examples=[604800], description="Seconds.")
