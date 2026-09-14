"""Seed data must be usable through the API it ships with.

The demo accounts were originally seeded at `@aigov.local`. `.local` is a reserved
special-use name that `email-validator` rejects, so `POST /auth/login` answered 422 for
the credentials the README documents, and every response that serialised one of those
users raised a validation error. The seeder writes through the ORM, which does no such
validation, so nothing caught it until a request was made.

These tests validate the shipped seed data against the very schemas the API uses.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.principal import SYSTEM_USER_EMAIL
from app.db.seed import (
    ADMIN_EMAIL,
    DEMO_EMAIL_DOMAIN,
    DEMO_PASSWORD,
    JURISDICTIONS,
    LEGACY_DEMO_EMAIL_DOMAIN,
    USERS,
    migrate_legacy_demo_emails,
)
from app.models.enums import UserRole
from app.schemas.auth import LoginRequest, UserCreate, UserRead

SEEDED_EMAILS = [u["email"] for u in USERS]


class TestSeededAccountsAreUsable:
    @pytest.mark.parametrize("email", SEEDED_EMAILS)
    def test_seeded_email_can_be_used_to_log_in(self, email: str):
        """The exact request the README tells a new user to make."""
        assert LoginRequest(email=email, password=DEMO_PASSWORD).email == email

    @pytest.mark.parametrize("email", [*SEEDED_EMAILS, SYSTEM_USER_EMAIL])
    def test_seeded_email_survives_serialisation(self, email: str, admin_user):
        """`/auth/me` and `/auth/users` must not 500 on a seeded row."""
        admin_user.email = email
        assert UserRead.model_validate(admin_user).email == email

    @pytest.mark.parametrize("email", SEEDED_EMAILS)
    def test_seeded_email_would_be_accepted_by_the_create_endpoint(self, email: str):
        assert (
            UserCreate(
                email=email, full_name="x", password=DEMO_PASSWORD, role=UserRole.VIEWER
            ).email
            == email
        )

    def test_demo_password_meets_the_schema_minimum(self):
        assert len(DEMO_PASSWORD) >= 8

    def test_demo_domain_is_a_reserved_documentation_domain(self):
        # RFC 2606: example.com is reserved and can never route.
        assert DEMO_EMAIL_DOMAIN.endswith("example.com")

    def test_the_broken_legacy_domain_is_actually_rejected(self):
        """Guard the assumption behind this whole module."""
        with pytest.raises(ValidationError):
            LoginRequest(email=f"admin@{LEGACY_DEMO_EMAIL_DOMAIN}", password=DEMO_PASSWORD)

    def test_roles_cover_the_documented_matrix(self):
        assert {u["role"] for u in USERS} == {
            UserRole.ADMIN,
            UserRole.RISK_OFFICER,
            UserRole.VIEWER,
        }

    def test_admin_constant_matches_the_seeded_admin(self):
        admin = next(u for u in USERS if u["role"] == UserRole.ADMIN)
        assert admin["email"] == ADMIN_EMAIL


class TestSeededJurisdictions:
    """Seed dictionaries must carry every key the seeder reads.

    A missing key here crashes `scripts/seed.py`, which runs in the container
    entrypoint — so one absent field takes down the API, worker and beat together.
    """

    @pytest.mark.parametrize("jurisdiction", JURISDICTIONS, ids=lambda j: j["code"])
    def test_required_keys_present(self, jurisdiction):
        for key in ("code", "name", "territories", "overlay_config", "risk_taxonomy"):
            assert key in jurisdiction, f"{jurisdiction['code']} is missing '{key}'"

    @pytest.mark.parametrize("jurisdiction", JURISDICTIONS, ids=lambda j: j["code"])
    def test_triggers_are_a_list_of_known_names(self, jurisdiction):
        from app.services.jurisdiction_engine import TRIGGER_REGISTRY

        triggers = jurisdiction["overlay_config"].get("triggers", [])
        assert isinstance(triggers, list), "triggers must be a list of registered names"
        unknown = [t for t in triggers if t not in TRIGGER_REGISTRY]
        assert not unknown, f"{jurisdiction['code']} references unknown triggers: {unknown}"

    def test_seeding_jurisdictions_is_idempotent(self, db):
        """The entrypoint seeds on every start, so a second run must not fail."""
        from app.db.seed import seed_jurisdictions

        seed_jurisdictions(db)
        seed_jurisdictions(db)  # the update branch is what regressed


class TestLegacyEmailRepair:
    """An already-seeded database must heal itself, not accumulate broken rows."""

    def _legacy_user(self, db, local_part: str = "admin"):
        from app.core.security import hash_password
        from app.models.user import User

        user = User(
            email=f"{local_part}@{LEGACY_DEMO_EMAIL_DOMAIN}",
            full_name="Legacy Demo",
            role=UserRole.ADMIN,
            hashed_password=hash_password(DEMO_PASSWORD),
            is_active=True,
            is_deleted=False,
        )
        db.add(user)
        db.flush()
        return user

    def test_legacy_row_is_renamed(self, db):
        user = self._legacy_user(db)
        assert migrate_legacy_demo_emails(db) == 1

        assert user.email == ADMIN_EMAIL
        # Now usable through the API schemas.
        LoginRequest(email=user.email, password=DEMO_PASSWORD)
        UserRead.model_validate(user)

    def test_duplicate_is_retired_rather_than_colliding(self, db):
        from app.core.security import hash_password
        from app.models.user import User

        db.add(
            User(
                email=ADMIN_EMAIL,
                full_name="Current Admin",
                role=UserRole.ADMIN,
                hashed_password=hash_password(DEMO_PASSWORD),
                is_active=True,
                is_deleted=False,
            )
        )
        db.flush()
        legacy = self._legacy_user(db)

        assert migrate_legacy_demo_emails(db) == 1
        assert legacy.is_deleted is True
        assert legacy.is_active is False

    def test_migration_is_idempotent(self, db):
        self._legacy_user(db)
        assert migrate_legacy_demo_emails(db) == 1
        assert migrate_legacy_demo_emails(db) == 0

    def test_unrelated_users_are_untouched(self, db, admin_user):
        original = admin_user.email
        self._legacy_user(db, local_part="viewer")
        migrate_legacy_demo_emails(db)
        assert admin_user.email == original
