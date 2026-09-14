"""User management and credential verification."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.security import hash_password, verify_password
from app.models.enums import AuditAction
from app.models.user import User
from app.schemas.auth import UserCreate, UserUpdate
from app.services.audit import record_audit


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: uuid.UUID) -> User:
        user = self.db.execute(
            select(User).where(User.id == user_id, User.is_deleted.is_(False))
        ).scalar_one_or_none()
        if user is None:
            raise NotFoundError(f"User {user_id} not found.")
        return user

    def get_by_email(self, email: str) -> User | None:
        return self.db.execute(
            select(User).where(func.lower(User.email) == email.lower(), User.is_deleted.is_(False))
        ).scalar_one_or_none()

    def list_users(self, *, offset: int = 0, limit: int = 100) -> tuple[list[User], int]:
        stmt = select(User).where(User.is_deleted.is_(False))
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
        return list(self.db.execute(stmt).scalars().all()), total

    def create(self, payload: UserCreate, actor: User | None = None) -> User:
        user = User(
            email=payload.email.lower(),
            full_name=payload.full_name,
            role=payload.role,
            hashed_password=hash_password(payload.password),
        )
        self.db.add(user)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(f"A user with email '{payload.email}' already exists.") from exc
        record_audit(
            self.db,
            resource_type="user",
            resource_id=user.id,
            action=AuditAction.CREATE,
            actor=actor,
            new_values={"email": user.email, "role": str(user.role)},
        )
        return user

    def update(self, user_id: uuid.UUID, payload: UserUpdate, actor: User) -> User:
        user = self.get(user_id)
        data = payload.model_dump(exclude_unset=True)
        if password := data.pop("password", None):
            user.hashed_password = hash_password(password)
        for field, value in data.items():
            setattr(user, field, value)
        self.db.flush()
        record_audit(
            self.db,
            resource_type="user",
            resource_id=user.id,
            action=AuditAction.UPDATE,
            actor=actor,
            new_values={k: str(v) for k, v in data.items()},
        )
        return user

    def authenticate(self, email: str, password: str) -> User:
        user = self.get_by_email(email)
        if user is not None and user.is_system:
            # The reserved principal has no usable credentials by construction; refuse
            # before touching the hash so it cannot be probed by timing either.
            raise AuthenticationError("Incorrect email or password.")
        if user is None or not verify_password(password, user.hashed_password):
            # Same message for both cases: do not leak which emails exist.
            raise AuthenticationError("Incorrect email or password.")
        if not user.is_active:
            raise AuthenticationError("This account is disabled.")
        record_audit(
            self.db,
            resource_type="user",
            resource_id=user.id,
            action=AuditAction.LOGIN,
            actor=user,
        )
        return user
