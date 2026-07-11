from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.alertmanager.client import AlertmanagerClient
from app.alertmanager.exceptions import AlertmanagerError
from app.alertmanager.forms import AlertmanagerConfigForm
from app.alertmanager.metrics import normalize_alertmanager_alerts
from app.extensions import db
from app.models.alertmanager import AlertmanagerConfig
from app.models.cluster import Cluster


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
    config.updated_at = datetime.now(
        UTC,
    )

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
            'error': 'Alertmanager endpoint is not configured.',
            'reason': 'AlertmanagerNotConfigured',
        }

    client = build_alertmanager_client(
        config,
    )

    try:
        result = client.test_connection()
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
            'connected': False,
            'label': 'Alertmanager Disconnected',
            'response_time_ms': None,
            'version': None,
            'error': str(
                exc,
            ),
            'reason': type(exc).__name__,
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
            'connected': False,
            'label': 'Alertmanager Error',
            'response_time_ms': None,
            'version': None,
            'error': str(
                exc,
            ),
            'reason': type(exc).__name__,
        }

    mark_alertmanager_status(
        config=config,
        status='connected',
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
        'connected': True,
        'label': 'Alertmanager Connected',
        'response_time_ms': result.get(
            'response_time_ms',
        ),
        'version': result.get(
            'version',
        ),
        'error': None,
        'reason': None,
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
    config.updated_at = datetime.now(
        UTC,
    )

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
