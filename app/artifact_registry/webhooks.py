from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

from celery.exceptions import CeleryError
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.artifact_registry.sync_jobs import enqueue_registry_target_refresh
from app.extensions.db import db
from app.integrations.registry.webhook_configuration import disable_webhook, generate_webhook_token
from app.models.integration import IntegrationInstance
from app.models.registry import RegistryWebhookEndpoint, RegistryWebhookEvent


class RegistryWebhookAuthError(PermissionError):
    pass


def _authenticate(endpoint: RegistryWebhookEndpoint, token: str) -> None:
    candidate = hashlib.sha256(str(token or '').encode()).hexdigest()
    if not endpoint.enabled or not endpoint.token_digest or not hmac.compare_digest(endpoint.token_digest, candidate):
        raise RegistryWebhookAuthError('Registry webhook authentication failed.')


def _resource_fields(payload: dict[str, Any]) -> dict[str, str | None]:
    raw_event_data = payload.get('event_data')
    event_data = raw_event_data if isinstance(raw_event_data, dict) else {}
    raw_repository = event_data.get('repository')
    repository = raw_repository if isinstance(raw_repository, dict) else {}
    raw_resources = event_data.get('resources')
    resources = raw_resources if isinstance(raw_resources, list) else []
    resource = next((item for item in resources if isinstance(item, dict)), {})
    repo_name = str(repository.get('repo_full_name') or repository.get('name') or '').strip()
    project_name = str(repository.get('namespace') or '').strip()
    if not project_name and '/' in repo_name:
        project_name, repo_name = repo_name.split('/', 1)
    return {
        'project_name': project_name or None,
        'repository_name': repo_name or None,
        'artifact_digest': str(resource.get('digest') or '').strip() or None,
        'artifact_tag': str(resource.get('tag') or '').strip() or None,
    }


def ingest_webhook(
    *,
    integration_instance_id: int,
    token: str,
    payload: dict[str, Any],
) -> tuple[RegistryWebhookEvent, bool]:
    endpoint = db.session.get(RegistryWebhookEndpoint, integration_instance_id)
    if endpoint is None:
        raise RegistryWebhookAuthError('Registry webhook endpoint is not configured.')
    _authenticate(endpoint, token)

    identity = db.session.get(IntegrationInstance, integration_instance_id)
    if identity is None or identity.integration_type != 'registry':
        raise LookupError('Registry integration does not exist.')

    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
    payload_digest = hashlib.sha256(canonical.encode()).hexdigest()
    provider_event_id = (
        str(payload.get('id') or payload.get('event_id') or payload.get('occur_at') or '').strip() or None
    )
    event_type = str(payload.get('type') or payload.get('event_type') or 'UNKNOWN').strip()
    dedup_source = f'{provider_event_id or ""}:{event_type}:{payload_digest}'
    dedup_key = hashlib.sha256(dedup_source.encode()).hexdigest()

    existing = RegistryWebhookEvent.query.filter_by(
        integration_instance_id=integration_instance_id,
        dedup_key=dedup_key,
    ).first()
    if existing is not None:
        endpoint.last_event_at = datetime.now(UTC)
        endpoint.last_status = 'duplicate'
        db.session.commit()
        return existing, False

    fields = _resource_fields(payload)
    event = RegistryWebhookEvent()
    event.integration_instance_id = integration_instance_id
    event.dedup_key = dedup_key
    event.provider_event_id = provider_event_id
    event.event_type = event_type[:120]
    event.payload_digest = payload_digest
    event.project_name = fields['project_name']
    event.repository_name = fields['repository_name']
    event.artifact_digest = fields['artifact_digest']
    event.artifact_tag = fields['artifact_tag']
    event.status = 'received'
    event.metadata_json = {
        'source': 'provider_webhook',
        'payload_retained': False,
    }
    db.session.add(event)
    db.session.flush()

    try:
        job, created = enqueue_registry_target_refresh(
            integration_instance_id=integration_instance_id,
            requested_by_user_id=None,
            trigger_type='webhook',
            scope_hint={
                'event_type': event_type,
                'project_name': fields['project_name'],
                'repository_name': fields['repository_name'],
                'artifact_digest': fields['artifact_digest'],
                'artifact_tag': fields['artifact_tag'],
            },
        )
    except (CeleryError, KombuOperationalError, OSError, RuntimeError, ValueError, SQLAlchemyError) as exc:
        event.status = 'refresh_failed'
        event.processed_at = datetime.now(UTC)
        event.metadata_json = {
            **(event.metadata_json or {}),
            'refresh_error_type': type(exc).__name__,
        }
        endpoint.last_status = 'refresh_failed'
        endpoint.last_error = str(exc)[:1000]
    else:
        event.status = 'queued' if created else 'deduplicated_refresh'
        event.job_execution_id = job.id
        event.processed_at = datetime.now(UTC)
        endpoint.last_status = event.status
        endpoint.last_error = None

    endpoint.last_event_at = datetime.now(UTC)
    db.session.commit()
    return event, True
