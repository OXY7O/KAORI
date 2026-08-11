from __future__ import annotations

import logging
from typing import Any

from celery.exceptions import CeleryError
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.integrations.contracts import IntegrationNotRegistered
from app.integrations.registry import get_integration
from app.integrations.validation.tasks import enqueue_runtime_refresh
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
        .order_by(IntegrationInstance.provider_type.asc(), IntegrationInstance.id.asc())
        .all()
    )
    provider_ids: dict[str, list[int]] = {}
    for identity in identities:
        try:
            module = get_integration(identity.provider_type)
        except IntegrationNotRegistered:
            logger.exception('Could not resolve registered provider %s for runtime refresh.', identity.provider_type)
            continue
        if 'runtime.health' not in module.operations:
            continue
        record = module.get_record_for_canonical(identity.id)
        record_id = getattr(record, 'id', None)
        if record_id is None:
            logger.warning(
                'Canonical integration %s:%s has no provider record; skipping runtime refresh.',
                identity.provider_type,
                identity.id,
            )
            continue
        provider_ids.setdefault(identity.provider_type, []).append(int(record_id))

    result: dict[str, Any] = {'queued': 0, 'skipped': 0, 'providers': {}}
    for provider_type, instance_ids in provider_ids.items():
        provider_result: dict[str, Any] = {'queued': 0, 'skipped': 0, 'tasks': []}
        for instance_id in instance_ids:
            try:
                task_id = enqueue_runtime_refresh(
                    provider_type=provider_type,
                    instance_id=int(instance_id),
                )
            except (CeleryError, KombuOperationalError, OSError, RuntimeError, SQLAlchemyError, ValueError) as exc:
                logger.exception(
                    'Could not enqueue runtime refresh for %s instance %s.',
                    provider_type,
                    instance_id,
                )
                provider_result['skipped'] += 1
                result['skipped'] += 1
                provider_result['tasks'].append({'instance_id': instance_id, 'error': str(exc)[:300]})
                continue
            if task_id is None:
                provider_result['skipped'] += 1
                result['skipped'] += 1
                provider_result['tasks'].append({'instance_id': instance_id, 'status': 'already_active'})
                continue
            provider_result['queued'] += 1
            result['queued'] += 1
            provider_result['tasks'].append({'instance_id': instance_id, 'task_id': task_id})
        result['providers'][provider_type] = provider_result
    return result
