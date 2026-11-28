"""Shared pilot reservation resource keys and transactional conflict guard."""

from __future__ import annotations

from hashlib import sha256
from ipaddress import IPv4Address

from sqlalchemy import select

from app.extensions.db import db
from app.models.automation import AutomationRunTargetClaim
from app.platform_operations.jobs.service import acquire_resource_admission_locks


def connection_resource(connection_id: int) -> str:
    return f'kubespray:connection:{connection_id}'


def host_resource(host_id: str) -> str:
    return f'kubespray:host:{host_id}'


def endpoint_resource(address: str) -> str:
    # Deliberately global until independently qualified network identity exists.
    canonical = str(IPv4Address(address))
    return 'kubespray:endpoint:' + sha256(canonical.encode('ascii')).hexdigest()


def has_active_target_claim(*keys: str) -> bool:
    """Hold canonical resource locks until caller commits or rolls back.

    All normal inventory writers and the reservation writer use these same
    keys. Database uniqueness remains the durable exclusion authority.
    """
    acquire_resource_admission_locks(*sorted(set(keys)))
    return db.session.execute(
        select(AutomationRunTargetClaim.id)
        .where(AutomationRunTargetClaim.active_resource_key.in_(keys))
        .limit(1)
    ).scalar_one_or_none() is not None
