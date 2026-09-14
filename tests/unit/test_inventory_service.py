from __future__ import annotations

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import SystemStatus
from app.schemas.common import PaginationParams
from app.schemas.system import (
    AISystemCreate,
    AISystemUpdate,
    SystemFilters,
    SystemMetadataBase,
    SystemMetadataUpdate,
)
from app.services.inventory import InventoryService


def _payload(name: str = "Fraud Scorer") -> AISystemCreate:
    return AISystemCreate(
        name=name,
        description=f"{name} description",
        status=SystemStatus.ACTIVE,
        system_metadata=SystemMetadataBase(
            purpose="Score transactions",
            use_case="credit_scoring",
            industry="fintech",
            deployment_regions=["EU"],
        ),
    )


def test_create_writes_initial_version(db, admin_user):
    service = InventoryService(db)
    system = service.create(_payload(), actor=admin_user)

    assert system.owner_id == admin_user.id
    assert system.metadata_version == 1
    versions = service.list_versions(system.id)
    assert len(versions) == 1
    assert versions[0].change_summary == "Initial creation"


def test_duplicate_name_conflicts(db, admin_user):
    service = InventoryService(db)
    service.create(_payload(), actor=admin_user)
    with pytest.raises(ConflictError):
        service.create(_payload(), actor=admin_user)


def test_update_bumps_version_and_records_diff(db, admin_user):
    service = InventoryService(db)
    system = service.create(_payload(), actor=admin_user)

    service.update(
        system.id,
        AISystemUpdate(
            description="Now also scores merchants",
            system_metadata=SystemMetadataUpdate(industry="payments"),
            change_summary="Broadened scope",
        ),
        actor=admin_user,
    )

    assert system.metadata_version == 2
    latest = service.list_versions(system.id)[0]
    assert latest.change_summary == "Broadened scope"
    assert latest.diff["system_metadata"]["industry"] == ["fintech", "payments"]


def test_noop_update_does_not_create_version(db, admin_user):
    service = InventoryService(db)
    system = service.create(_payload(), actor=admin_user)
    service.update(system.id, AISystemUpdate(description=system.description), actor=admin_user)
    assert system.metadata_version == 1
    assert len(service.list_versions(system.id)) == 1


def test_soft_delete_hides_then_restore_returns(db, admin_user):
    service = InventoryService(db)
    system = service.create(_payload(), actor=admin_user)

    service.soft_delete(system.id, actor=admin_user)
    with pytest.raises(NotFoundError):
        service.get(system.id)
    assert service.get(system.id, include_deleted=True).is_deleted is True

    service.restore(system.id, actor=admin_user)
    assert service.get(system.id).is_deleted is False


def test_search_and_filter(db, admin_user):
    service = InventoryService(db)
    service.create(_payload("Fraud Scorer"), actor=admin_user)
    service.create(_payload("Support Copilot"), actor=admin_user)

    items, total = service.list_systems(SystemFilters(q="fraud"), PaginationParams())
    assert total == 1
    assert items[0].name == "Fraud Scorer"

    items, total = service.list_systems(SystemFilters(industry="fintech"), PaginationParams())
    assert total == 2

    # deployment_region filtering uses JSONB containment, which is PostgreSQL-only;
    # it is covered by the integration suite rather than the SQLite unit fixture.

    items, total = service.list_systems(
        SystemFilters(status=[SystemStatus.DRAFT]), PaginationParams()
    )
    assert total == 0


def test_pagination(db, admin_user):
    service = InventoryService(db)
    for i in range(5):
        service.create(_payload(f"System {i}"), actor=admin_user)

    items, total = service.list_systems(SystemFilters(), PaginationParams(page=2, page_size=2))
    assert total == 5
    assert len(items) == 2
