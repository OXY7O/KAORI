from __future__ import annotations

from typing import Any

from app.integrations.alertmanager.client_factory import build_client
from app.integrations.alertmanager.contracts import AlertQuery
from app.integrations.alertmanager.exceptions import AlertmanagerError
from app.integrations.alertmanager.normalizers.alerts import normalize_alerts
from app.integrations.alertmanager.normalizers.silences import normalize_silences
from app.integrations.alertmanager.status import mark_status
from app.models.alertmanager import AlertmanagerInstance


def read_alerts(
    source: AlertmanagerInstance,
    *,
    source_name: str,
    query: AlertQuery | None = None,
    canonical_instance_id: int | None = None,
) -> dict[str, Any]:
    gate_error = _runtime_gate_error(source)
    if gate_error:
        return _failure_payload('alerts', gate_error)

    query = query or AlertQuery()
    client = build_client(source)
    try:
        raw_alerts = client.get_alerts(
            active=query.active,
            silenced=query.silenced,
            inhibited=query.inhibited,
            unprocessed=query.unprocessed,
            receiver=query.receiver,
            filters=list(query.filters) or None,
        )
    except AlertmanagerError as exc:
        mark_status(source, status='disconnected', error=str(exc), response_time_ms=None)
        return _failure_payload('alerts', str(exc))

    return {
        'source': 'alertmanager',
        'source_instance_id': canonical_instance_id,
        'source_instance_name': source_name,
        'connected': True,
        'alerts': normalize_alerts(
            raw_alerts,
            source_instance_id=canonical_instance_id,
            source_instance_name=source_name,
        ),
        'error': None,
    }


def read_silences(
    source: AlertmanagerInstance,
    *,
    source_name: str,
    filters: tuple[str, ...] = (),
    canonical_instance_id: int | None = None,
) -> dict[str, Any]:
    gate_error = _runtime_gate_error(source)
    if gate_error:
        return _failure_payload('silences', gate_error)

    client = build_client(source)
    try:
        raw_silences = client.get_silences(filters=list(filters) or None)
    except AlertmanagerError as exc:
        mark_status(source, status='disconnected', error=str(exc), response_time_ms=None)
        return _failure_payload('silences', str(exc))

    return {
        'source': 'alertmanager',
        'source_instance_id': canonical_instance_id,
        'source_instance_name': source_name,
        'connected': True,
        'silences': normalize_silences(
            raw_silences,
            source_instance_id=canonical_instance_id,
            source_instance_name=source_name,
        ),
        'error': None,
    }


def _runtime_gate_error(source: AlertmanagerInstance) -> str | None:
    if not source.endpoint:
        return 'Alertmanager endpoint is not configured.'
    if source.readiness_status in {'blocked', 'validation_required'}:
        return source.validation_message or 'Alertmanager integration is not validated for runtime use.'
    return None


def _failure_payload(collection_name: str, error: str) -> dict[str, Any]:
    return {
        'source': 'alertmanager',
        'connected': False,
        collection_name: [],
        'error': error,
    }
