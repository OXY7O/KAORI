"""Atomic, source-only Linux host enrollment for one Ansible connection (#5168).

A registered host is inventory *intent*, not a verified SSH identity or
an authorization to execute Ansible/Kubespray.
"""

from __future__ import annotations

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
    if AutomationInventoryAssignment.query.filter_by(integration_instance_id=connection.id).count() >= _HOST_LIMIT:
        raise AutomationInventoryDenied('The connection has reached the approved host inventory limit.')
    if AutomationHostAsset.query.filter_by(environment=intent.environment, name=intent.name).first():
        raise AutomationInventoryDenied('The host name is already registered in this environment.')
    if AutomationHostAsset.query.filter_by(environment=intent.environment, address=intent.address).first():
        raise AutomationInventoryDenied('The host address is already registered in this environment.')

    host = AutomationHostAsset(
        name=intent.name,
        environment=intent.environment,
        address=intent.address,
        ssh_port=intent.ssh_port,
        lifecycle_status='registered',
    )
    membership = AutomationInventoryAssignment(
        integration_instance_id=connection.id,
        host=host,
        role=role,
        enabled=True,
    )
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
