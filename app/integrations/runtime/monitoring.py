from __future__ import annotations

import logging
from typing import Any

from celery.exceptions import CeleryError
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.integrations.contracts import IntegrationNotRegistered
from app.integrations.registry import get_integration
from app.integrations.validation.scheduling import enqueue_runtime_refresh
from app.models.integration import IntegrationInstance

logger = logging.getLogger(__name__)

__all__ = ['dispatch_integration_runtime_refresh']


def dispatch_integration_runtime_refresh() -> dict[str, object]:
    """Queue independent runtime refresh jobs for all enabled registered providers."""
    identities = (
        IntegrationInstance.query.filter(
            IntegrationInstance.enabled.is_(True),
            IntegrationInstance.lifecycle_status == 'active',
        )
        .order_by(IntegrationInstance.integration_type.asc(), IntegrationInstance.id.asc())
        .all()
    )
    integration_ids: dict[str, list[int]] = {}
    for identity in identities:
        try:
            module = get_integration(identity.integration_type)
        except IntegrationNotRegistered:
            logger.exception('Could not resolve registered provider %s for runtime refresh.', identity.integration_type)
            continue
        if 'runtime.health' not in module.operations:
            continue
        if module.get_record_for_canonical(identity.id) is None:
            logger.warning(
                'Canonical integration %s:%s has no provider implementation record; skipping runtime refresh.',
                identity.integration_type,
                identity.id,
            )
            continue
        integration_ids.setdefault(identity.integration_type, []).append(int(identity.id))

    result: dict[str, Any] = {'queued': 0, 'skipped': 0, 'integration_types': {}}
    for integration_type, integration_instance_ids in integration_ids.items():
        type_result: dict[str, Any] = {'queued': 0, 'skipped': 0, 'tasks': []}
        for integration_instance_id in integration_instance_ids:
            try:
                task_id = enqueue_runtime_refresh(
                    integration_type=integration_type,
                    integration_instance_id=integration_instance_id,
                )
            except (CeleryError, KombuOperationalError, OSError, RuntimeError, SQLAlchemyError, ValueError) as exc:
                logger.exception(
                    'Could not enqueue runtime refresh for %s instance %s.',
                    integration_type,
                    integration_instance_id,
                )
                type_result['skipped'] += 1
                result['skipped'] += 1
                type_result['tasks'].append(
                    {'integration_instance_id': integration_instance_id, 'error': str(exc)[:300]}
                )
                continue
            if task_id is None:
                type_result['skipped'] += 1
                result['skipped'] += 1
                type_result['tasks'].append(
                    {'integration_instance_id': integration_instance_id, 'status': 'already_active'}
                )
                continue
            type_result['queued'] += 1
            result['queued'] += 1
            type_result['tasks'].append({'integration_instance_id': integration_instance_id, 'task_id': task_id})
        result['integration_types'][integration_type] = type_result
    return result
