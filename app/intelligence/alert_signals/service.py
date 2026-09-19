from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.resolver import (
    connection_for_cluster,
)
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.tls import weak_tls_context
from app.integrations.registry import get_integration
from app.intelligence.alert_signals.config import alert_signal_freshness_minutes
from app.models import AlertSignalSnapshot, Cluster

KUBERNETES_RUNTIME_HEALTH_PROFILE = 'kubernetes_runtime_health'
KUBERNETES_RUNTIME_HEALTH_SIGNAL = 'kubernetes.runtime_health'
_SIGNAL_SCHEMA_VERSION = 1


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _value(obj: Any, *names: str, default: Any = None) -> Any:
    if obj is None:
        return default
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def _pod_signal_rows(core_api: Any) -> list[dict[str, Any]]:
    response = core_api.list_pod_for_all_namespaces(watch=False)
    rows: list[dict[str, Any]] = []
    for pod in list(_value(response, 'items', default=[]) or []):
        metadata = _value(pod, 'metadata')
        status = _value(pod, 'status')
        spec = _value(pod, 'spec')
        restart_count = sum(
            int(_value(item, 'restart_count', 'restartCount', default=0) or 0)
            for item in list(_value(status, 'container_statuses', 'containerStatuses', default=[]) or [])
        )
        rows.append(
            {
                'namespace': str(_value(metadata, 'namespace', default='default') or 'default'),
                'pod_name': str(_value(metadata, 'name', default='pod') or 'pod'),
                'node_name': str(_value(spec, 'node_name', 'nodeName', default='') or ''),
                'phase': str(_value(status, 'phase', default='Unknown') or 'Unknown'),
                'restart_count': restart_count,
            }
        )
    return rows


def _node_signal_rows(core_api: Any) -> list[dict[str, Any]]:
    response = core_api.list_node(watch=False)
    rows: list[dict[str, Any]] = []
    for node in list(_value(response, 'items', default=[]) or []):
        metadata = _value(node, 'metadata')
        status = _value(node, 'status')
        ready = False
        for condition in list(_value(status, 'conditions', default=[]) or []):
            if str(_value(condition, 'type', default='') or '') != 'Ready':
                continue
            ready = str(_value(condition, 'status', default='') or '').lower() == 'true'
            break
        rows.append(
            {
                'node_name': str(_value(metadata, 'name', default='node') or 'node'),
                'ready': ready,
            }
        )
    return rows


def _snapshot(*, cluster_id: str) -> AlertSignalSnapshot | None:
    return AlertSignalSnapshot.query.filter_by(
        domain='kubernetes',
        asset_key=str(cluster_id),
        signal_key=KUBERNETES_RUNTIME_HEALTH_SIGNAL,
    ).first()


def _get_or_create_snapshot(*, cluster_id: str) -> AlertSignalSnapshot:
    snapshot = _snapshot(cluster_id=cluster_id)
    if snapshot is not None:
        return snapshot
    snapshot = AlertSignalSnapshot()
    snapshot.domain = 'kubernetes'
    snapshot.asset_key = str(cluster_id)
    snapshot.signal_key = KUBERNETES_RUNTIME_HEALTH_SIGNAL
    snapshot.status = 'failed'
    db.session.add(snapshot)
    return snapshot


def refresh_kubernetes_runtime_signal(cluster: Cluster) -> AlertSignalSnapshot:
    """Collect only runtime signals needed by fast Alert Intelligence rules."""

    if str(cluster.status or '').lower() != 'connected':
        raise RuntimeError('Kubernetes cluster runtime is not connected.')

    connection = connection_for_cluster(cluster)
    instance = connection.integration_instance
    if not instance.enabled or instance.lifecycle_status != 'active':
        raise RuntimeError('The canonical Kubernetes integration is not active for alert signal evaluation.')

    client = get_integration('container_orchestrator').execute('client.build', connection)
    with weak_tls_context(enabled=bool(connection.allow_weak_tls)):
        core_api = client.core_api()
        pods = _pod_signal_rows(core_api)
        nodes = _node_signal_rows(core_api)

    now = _utcnow()
    snapshot = _get_or_create_snapshot(cluster_id=cluster.id)
    snapshot.status = 'ready'
    snapshot.payload_json = {
        'schema_version': _SIGNAL_SCHEMA_VERSION,
        'profile': KUBERNETES_RUNTIME_HEALTH_PROFILE,
        'cluster_id': str(cluster.id),
        'cluster_name': str(cluster.name),
        'pods': pods,
        'nodes': nodes,
    }
    snapshot.generated_at = now
    snapshot.expires_at = now + timedelta(minutes=alert_signal_freshness_minutes())
    snapshot.last_attempt_at = now
    snapshot.last_error = None
    db.session.commit()
    return snapshot


def fail_kubernetes_runtime_signal(cluster: Cluster, error: Exception | str) -> AlertSignalSnapshot:
    now = _utcnow()
    snapshot = _get_or_create_snapshot(cluster_id=cluster.id)
    snapshot.status = 'failed'
    snapshot.last_attempt_at = now
    snapshot.last_error = str(error)[:4000]
    db.session.commit()
    return snapshot


def refresh_all_kubernetes_runtime_signals() -> dict[str, Any]:
    refreshed = 0
    failed = 0
    failures: list[dict[str, str]] = []
    clusters = Cluster.query.order_by(Cluster.name.asc(), Cluster.id.asc()).all()
    for cluster in clusters:
        try:
            refresh_kubernetes_runtime_signal(cluster)
            refreshed += 1
        except (
            ApiException,
            ConfigException,
            SQLAlchemyError,
            RuntimeError,
            ValueError,
            LookupError,
            TypeError,
            OSError,
        ) as exc:
            db.session.rollback()
            fail_kubernetes_runtime_signal(cluster, exc)
            failed += 1
            failures.append(
                {
                    'cluster_id': str(cluster.id),
                    'cluster_name': str(cluster.name),
                    'error_type': type(exc).__name__,
                    'message': str(exc),
                }
            )
    return {
        'total': len(clusters),
        'refreshed': refreshed,
        'failed': failed,
        'failures': failures,
    }


def read_kubernetes_runtime_signal(cluster_id: str) -> dict[str, Any]:
    """Read the fast signal snapshot without performing provider I/O."""

    snapshot = _snapshot(cluster_id=str(cluster_id))
    if snapshot is None:
        return {'state': 'missing', 'payload': None, 'snapshot': None}
    if snapshot.status != 'ready' or snapshot.payload_json is None or snapshot.generated_at is None:
        return {'state': 'unavailable', 'payload': None, 'snapshot': snapshot}
    now = _utcnow()
    expires_at = _as_utc(snapshot.expires_at) if snapshot.expires_at else _as_utc(snapshot.generated_at)
    if now > expires_at:
        return {'state': 'stale', 'payload': None, 'snapshot': snapshot}
    return {'state': 'fresh', 'payload': dict(snapshot.payload_json), 'snapshot': snapshot}


def alert_signal_source_posture(*, domain: str, asset_key: str, profile: str) -> tuple[bool, str] | None:
    """Return fast-signal source posture when one rule opts into a profile.

    ``None`` means no fast snapshot has ever been committed yet, so callers may
    temporarily retain the existing committed-inventory behavior during rollout.
    Once a snapshot exists, stale or failed evaluation becomes explicit source
    unavailability and must never masquerade as recovery.
    """

    if str(domain or '').strip().lower() != 'kubernetes':
        return None
    if str(profile or '').strip() != KUBERNETES_RUNTIME_HEALTH_PROFILE:
        return None
    result = read_kubernetes_runtime_signal(str(asset_key))
    if result['state'] == 'missing':
        return None
    if result['state'] == 'fresh':
        return True, ''
    return False, 'source_unavailable'


def runtime_signal_payloads() -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Return fresh runtime payloads plus clusters that have unusable fast evidence."""

    fresh: dict[str, dict[str, Any]] = {}
    unavailable: set[str] = set()
    rows = AlertSignalSnapshot.query.filter_by(domain='kubernetes', signal_key=KUBERNETES_RUNTIME_HEALTH_SIGNAL).all()
    for row in rows:
        result = read_kubernetes_runtime_signal(str(row.asset_key))
        if result['state'] == 'fresh' and isinstance(result['payload'], dict):
            fresh[str(row.asset_key)] = dict(result['payload'])
        else:
            unavailable.add(str(row.asset_key))
    return fresh, unavailable
