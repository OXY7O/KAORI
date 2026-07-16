from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.alertmanager.client import AlertmanagerClient
from app.alertmanager.exceptions import AlertmanagerError
from app.alertmanager.forms import AlertmanagerConfigForm
from app.alertmanager.metrics import normalize_alertmanager_alerts
from app.common.integration_errors import describe_integration_failure
from app.extensions import db
from app.models.alertmanager import AlertmanagerConfig
from app.models.cluster import Cluster
from app.integrations.compatibility import evaluate_compatibility

logger = logging.getLogger(__name__)


def get_cluster_by_id(
    cluster_id: str,
) -> Cluster | None:
    return db.session.get(
        Cluster,
        cluster_id,
    )


def get_alertmanager_config_by_cluster_id(
    cluster_id: str,
) -> AlertmanagerConfig | None:
    statement = select(
        AlertmanagerConfig,
    ).where(
        AlertmanagerConfig.cluster_id == cluster_id,
    )

    return db.session.execute(
        statement,
    ).scalar_one_or_none()


def get_or_create_alertmanager_config(
    cluster_id: str,
) -> AlertmanagerConfig:
    config = get_alertmanager_config_by_cluster_id(
        cluster_id,
    )

    if config is not None:
        return config

    config = AlertmanagerConfig()
    config.cluster_id = cluster_id
    config.endpoint = ''
    config.auth_type = 'none'
    config.timeout = 5
    config.verify_ssl = True

    db.session.add(
        config,
    )

    return config


def save_alertmanager_config(
    *,
    cluster_id: str,
    form: AlertmanagerConfigForm,
) -> AlertmanagerConfig:
    config = get_or_create_alertmanager_config(
        cluster_id,
    )

    config.endpoint = form.endpoint
    config.auth_type = form.auth_type
    config.username = form.username if form.auth_type == 'basic' else None
    config.password = form.password if form.auth_type == 'basic' else None
    config.bearer_token = form.bearer_token if form.auth_type == 'bearer' else None
    config.timeout = form.timeout
    config.verify_ssl = form.verify_ssl
    config.updated_at = datetime.now(UTC)
    config.compatibility_status = 'validation_required'
    config.readiness_status = 'validation_required'
    config.compatibility_profile = None
    config.validation_message = 'Configuration changed. Run validation before KAORI uses this integration.'
    config.last_validated_at = None

    db.session.commit()

    return config


def build_alertmanager_client(
    config: AlertmanagerConfig,
) -> AlertmanagerClient:
    return AlertmanagerClient(
        endpoint=config.endpoint,
        auth_type=config.auth_type,
        username=config.username,
        password=config.password,
        bearer_token=config.bearer_token,
        timeout=config.timeout,
        verify_ssl=config.verify_ssl,
    )


def test_alertmanager_connection(
    *,
    cluster_id: str,
) -> dict[str, Any]:
    config = get_alertmanager_config_by_cluster_id(
        cluster_id,
    )

    if config is None or not config.endpoint:
        return {
            'connected': False,
            'label': 'Alertmanager Not Configured',
            'response_time_ms': None,
            'version': None,
            'error': (
                'Alertmanager is not configured for this cluster. Save a valid endpoint and authentication '
                'configuration before running the connection test.'
            ),
            'reason': 'Integration is not configured',
            'failure_code': 'not_configured',
        }

    client = build_alertmanager_client(
        config,
    )

    try:
        result = client.test_connection()
    except AlertmanagerError as exc:
        failure = describe_integration_failure(
            exc,
            service_name='Alertmanager',
            endpoint=config.endpoint,
            request_path='/api/v2/status',
            timeout_seconds=min(max(int(config.timeout or 5), 1), 5),
        )
        logger.warning(
            'Alertmanager connection test failed for cluster %s: %s',
            cluster_id,
            exc,
            exc_info=True,
        )
        mark_alertmanager_status(
            config=config,
            status='disconnected',
            error=failure['detail'],
            response_time_ms=None,
        )

        return {
            'connected': False,
            'label': 'Alertmanager Disconnected',
            'response_time_ms': None,
            'version': None,
            'error': failure['detail'],
            'reason': failure['reason'],
            'failure_code': failure['code'],
            'endpoint_host': failure['endpoint_host'],
            'endpoint_port': failure['endpoint_port'],
            'request_path': failure['request_path'],
        }
    except Exception as exc:
        failure = describe_integration_failure(
            exc,
            service_name='Alertmanager',
            endpoint=config.endpoint,
            request_path='/api/v2/status',
            timeout_seconds=min(max(int(config.timeout or 5), 1), 5),
        )
        logger.exception(
            'Unexpected Alertmanager connection test failure for cluster %s.',
            cluster_id,
        )
        mark_alertmanager_status(
            config=config,
            status='error',
            error=failure['detail'],
            response_time_ms=None,
        )

        return {
            'connected': False,
            'label': 'Alertmanager Error',
            'response_time_ms': None,
            'version': None,
            'error': failure['detail'],
            'reason': failure['reason'],
            'failure_code': failure['code'],
            'endpoint_host': failure['endpoint_host'],
            'endpoint_port': failure['endpoint_port'],
            'request_path': failure['request_path'],
        }

    version = result.get('version') or 'unknown'
    capabilities = {'status_v2'}
    try:
        client.get_alerts()
        capabilities.add('alerts_v2')
        client.get_silences()
        capabilities.add('silences_v2')
    except AlertmanagerError as exc:
        logger.warning('Alertmanager capability validation failed for cluster %s: %s', cluster_id, exc)

    compatibility = evaluate_compatibility('alertmanager', version, capabilities=capabilities)
    config.detected_version = version
    config.compatibility_status = compatibility.status
    config.compatibility_profile = compatibility.profile_key
    config.capability_profile = 'alert-management-v1'
    config.readiness_status = compatibility.readiness
    config.validation_message = compatibility.message
    config.last_validated_at = datetime.now(UTC)

    mark_alertmanager_status(
        config=config,
        status='connected' if compatibility.readiness != 'blocked' else 'incompatible',
        error=None,
        response_time_ms=int(
            result.get(
                'response_time_ms',
                0,
            )
            or 0
        ),
    )

    return {
        'connected': compatibility.readiness != 'blocked',
        'label': 'Alertmanager Ready' if compatibility.readiness == 'ready' else 'Alertmanager Incompatible',
        'response_time_ms': result.get('response_time_ms'),
        'version': version,
        'compatibility_status': compatibility.status,
        'readiness_status': compatibility.readiness,
        'compatibility_profile': compatibility.profile_key,
        'error': None if compatibility.readiness != 'blocked' else compatibility.message,
        'reason': compatibility.message,
        'failure_code': None if compatibility.readiness != 'blocked' else compatibility.status,
    }


def get_alertmanager_status(
    *,
    cluster_id: str,
) -> dict[str, Any]:
    config = get_alertmanager_config_by_cluster_id(
        cluster_id,
    )

    if config is None or not config.endpoint:
        return {
            'configured': False,
            'connected': False,
            'label': 'Not Configured',
            'response_time_ms': None,
            'last_checked_at': None,
            'error': None,
        }

    return {
        'configured': True,
        'connected': config.last_status == 'connected',
        'label': config.display_status,
        'response_time_ms': config.last_response_time_ms,
        'last_checked_at': config.last_checked_at,
        'error': config.last_error,
    }


def get_alertmanager_alerts(
    *,
    cluster_id: str,
) -> dict[str, Any]:
    config = get_alertmanager_config_by_cluster_id(
        cluster_id,
    )

    if config is None or not config.endpoint:
        return {
            'source': 'alertmanager',
            'connected': False,
            'alerts': [],
            'error': 'Alertmanager endpoint is not configured.',
        }

    if config.readiness_status in {'blocked', 'validation_required'}:
        return {
            'source': 'alertmanager',
            'connected': False,
            'alerts': [],
            'error': config.validation_message or 'Alertmanager integration is not validated for runtime use.',
        }

    client = build_alertmanager_client(
        config,
    )

    try:
        raw_alerts = client.get_alerts()
    except AlertmanagerError as exc:
        mark_alertmanager_status(
            config=config,
            status='disconnected',
            error=str(
                exc,
            ),
            response_time_ms=None,
        )

        return {
            'source': 'alertmanager',
            'connected': False,
            'alerts': [],
            'error': str(
                exc,
            ),
        }

    normalized_alerts = normalize_alertmanager_alerts(
        raw_alerts,
    )

    return {
        'source': 'alertmanager',
        'connected': True,
        'alerts': normalized_alerts,
        'error': None,
    }


def get_alertmanager_silences(
    *,
    cluster_id: str,
) -> dict[str, Any]:
    config = get_alertmanager_config_by_cluster_id(
        cluster_id,
    )

    if config is None or not config.endpoint:
        return {
            'source': 'alertmanager',
            'connected': False,
            'silences': [],
            'error': 'Alertmanager endpoint is not configured.',
        }

    if config.readiness_status in {'blocked', 'validation_required'}:
        return {
            'source': 'alertmanager',
            'connected': False,
            'silences': [],
            'error': config.validation_message or 'Alertmanager integration is not validated for runtime use.',
        }

    client = build_alertmanager_client(
        config,
    )

    try:
        silences = client.get_silences()
    except AlertmanagerError as exc:
        mark_alertmanager_status(
            config=config,
            status='disconnected',
            error=str(
                exc,
            ),
            response_time_ms=None,
        )

        return {
            'source': 'alertmanager',
            'connected': False,
            'silences': [],
            'error': str(
                exc,
            ),
        }
    except Exception as exc:
        mark_alertmanager_status(
            config=config,
            status='error',
            error=str(
                exc,
            ),
            response_time_ms=None,
        )

        return {
            'source': 'alertmanager',
            'connected': False,
            'silences': [],
            'error': str(
                exc,
            ),
        }

    return {
        'source': 'alertmanager',
        'connected': True,
        'silences': silences,
        'error': None,
    }


def mark_alertmanager_status(
    *,
    config: AlertmanagerConfig,
    status: str,
    error: str | None,
    response_time_ms: int | None,
) -> None:
    config.last_status = status
    config.last_error = error
    config.last_response_time_ms = response_time_ms
    config.last_checked_at = datetime.now(
        UTC,
    )
    config.updated_at = datetime.now(UTC)

    db.session.commit()


def build_alertmanager_config_context(
    *,
    cluster_id: str,
) -> dict[str, Any]:
    cluster = get_cluster_by_id(
        cluster_id,
    )
    config = get_alertmanager_config_by_cluster_id(
        cluster_id,
    )
    status = get_alertmanager_status(
        cluster_id=cluster_id,
    )

    return {
        'cluster': cluster,
        'config': config,
        'status': status,
    }
