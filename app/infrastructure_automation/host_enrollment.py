"""Atomic, source-only Linux host enrollment for one Ansible connection (#5168).

A registered host is inventory *intent*, not a verified SSH identity or
an authorization to execute Ansible/Kubespray.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions.db import db
from app.infrastructure_automation.host_registry import (
    AutomationHostIntent,
    AutomationInventoryDenied,
    require_ansible_connection,
    validate_host_intent,
)
from app.models.automation import AutomationHostAsset, AutomationInventoryAssignment
from app.models.integration import IntegrationInstance

_HOST_LIMIT = 256
_INVENTORY_ROLES = frozenset({'control_plane', 'worker'})


def get_enrollment_connection(connection_id: int) -> IntegrationInstance | None:
    """Resolve the selected connection through the application boundary."""
    return db.session.get(IntegrationInstance, connection_id)


def get_scoped_host_assignment(
    connection_id: int, host_id: str, *, lock: bool = False
) -> AutomationInventoryAssignment | None:
    """Resolve an active membership and lock its host for mutation when requested."""
    query = AutomationInventoryAssignment.query.filter_by(
        integration_instance_id=connection_id, host_id=host_id, enabled=True
    )
    if lock:
        query = query.with_for_update()
    assignment = query.first()
    if assignment is not None and lock:
        db.session.refresh(assignment.host, with_for_update=True)
    return assignment


def enroll_host_for_connection(
    connection: IntegrationInstance,
    values: AutomationHostIntent,
    *,
    role: str,
) -> AutomationHostAsset:
    """Create host identity and membership atomically, without SSH or secrets."""
    intent = validate_host_intent(values)
    require_ansible_connection(connection, environment=intent.environment)
    if type(connection.id) is not int or connection.id <= 0:
        raise AutomationInventoryDenied('The selected Ansible connection is invalid.')
    if role not in _INVENTORY_ROLES:
        raise AutomationInventoryDenied('Choose an approved Kubernetes host role.')

    # Never register a 257th member, even though the paginated read model
    # would show only the first five. An execution-bound snapshot is separate.
    if (
        AutomationInventoryAssignment.query.filter_by(integration_instance_id=connection.id, enabled=True).count()
        >= _HOST_LIMIT
    ):
        raise AutomationInventoryDenied('The connection has reached the approved host inventory limit.')
    if AutomationHostAsset.query.filter_by(environment=intent.environment, name=intent.name).first():
        raise AutomationInventoryDenied('The host name is already registered in this environment.')
    if AutomationHostAsset.query.filter_by(environment=intent.environment, address=intent.address).first():
        raise AutomationInventoryDenied('The host address is already registered in this environment.')

    host = AutomationHostAsset()
    host.name = intent.name
    host.environment = intent.environment
    host.address = intent.address
    host.ssh_port = intent.ssh_port
    host.lifecycle_status = 'registered'
    membership = AutomationInventoryAssignment()
    membership.integration_instance_id = connection.id
    membership.host = host
    membership.role = role
    membership.enabled = True
    try:
        db.session.add_all((host, membership))
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise AutomationInventoryDenied('The host identity or assignment is already registered.') from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return host


def host_revision(assignment: AutomationInventoryAssignment) -> str:
    """Deterministic, non-secret optimistic concurrency marker for the exact host membership."""
    host = assignment.host
    values = (
        host.id,
        host.name,
        host.environment,
        host.address,
        host.ssh_port,
        host.lifecycle_status,
        str(host.updated_at),
        assignment.id,
        assignment.integration_instance_id,
        assignment.role,
        assignment.enabled,
        str(assignment.updated_at),
    )
    return hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()


def _require_editable(
    connection: IntegrationInstance, assignment: AutomationInventoryAssignment, expected_revision: str
) -> AutomationHostAsset:
    """Fail closed for cross-connection, retired, shared, or stale assets."""
    environment = connection.environment
    if not isinstance(environment, str):
        raise AutomationInventoryDenied('A valid non-production connection environment is required.')
    require_ansible_connection(connection, environment=environment)
    host = assignment.host
    if (
        assignment.integration_instance_id != connection.id
        or not assignment.enabled
        or host is None
        or host.environment != connection.environment
        or host.lifecycle_status != 'registered'
    ):
        raise AutomationInventoryDenied('This host is not an active member of the selected connection.')
    # A shared host must not be silently changed for a second integration.
    if AutomationInventoryAssignment.query.filter_by(host_id=host.id, enabled=True).count() != 1:
        raise AutomationInventoryDenied('Shared host identities require independent ownership review.')
    if not expected_revision or expected_revision != host_revision(assignment):
        raise AutomationInventoryDenied('Host inventory changed. Reload and review the current host before saving.')
    return host


def update_host_for_connection(
    connection: IntegrationInstance,
    assignment: AutomationInventoryAssignment,
    values: AutomationHostIntent,
    *,
    role: str,
    expected_revision: str,
) -> AutomationHostAsset:
    """Update one exclusive host and role without changing its canonical ID."""
    host = _require_editable(connection, assignment, expected_revision)
    intent = validate_host_intent(values)
    if intent.environment != connection.environment or role not in _INVENTORY_ROLES:
        raise AutomationInventoryDenied('Host environment or Kubernetes role is not approved.')
    other_name = AutomationHostAsset.query.filter_by(environment=intent.environment, name=intent.name).first()
    other_address = AutomationHostAsset.query.filter_by(environment=intent.environment, address=intent.address).first()
    if (other_name is not None and other_name.id != host.id) or (
        other_address is not None and other_address.id != host.id
    ):
        raise AutomationInventoryDenied('Another host already owns the requested name or address.')
    host.name = intent.name
    host.address = intent.address
    host.ssh_port = intent.ssh_port
    assignment.role = role
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise AutomationInventoryDenied('The host identity conflicts with an existing record.') from exc
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return host


def retire_host_for_connection(
    connection: IntegrationInstance,
    assignment: AutomationInventoryAssignment,
    *,
    expected_revision: str,
    confirmation: str,
) -> AutomationHostAsset:
    """Soft-retire an exclusively owned host; preserve evidence and revoke current membership."""
    host = _require_editable(connection, assignment, expected_revision)
    if confirmation != host.name:
        raise AutomationInventoryDenied('Type the exact host name to confirm retirement.')
    assignment.enabled = False
    host.lifecycle_status = 'retired'
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return host
