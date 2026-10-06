from __future__ import annotations

from typing import Any

from app.integrations.observability.alert_source.providers.alertmanager.contracts import CanonicalAlert
from app.integrations.observability.alert_source.providers.alertmanager.normalizers.time import (
    human_duration,
    parse_datetime,
)


def normalize_alerts(
    alerts: list[dict[str, Any]],
    *,
    source_instance_id: int | None,
    source_instance_name: str,
) -> list[dict[str, Any]]:
    return [
        normalize_alert(
            alert,
            source_instance_id=source_instance_id,
            source_instance_name=source_instance_name,
        ).to_dict()
        for alert in alerts
    ]


def normalize_alert(
    alert: dict[str, Any],
    *,
    source_instance_id: int | None,
    source_instance_name: str,
) -> CanonicalAlert:
    labels = _safe_dict(alert.get('labels'))
    annotations = _safe_dict(alert.get('annotations'))
    status = _safe_dict(alert.get('status'))
    starts_at = parse_datetime(alert.get('startsAt'))
    ends_at = parse_datetime(alert.get('endsAt'))
    silenced_by = _string_tuple(status.get('silencedBy'))
    inhibited_by = _string_tuple(status.get('inhibitedBy'))
    alert_name = _value(labels, 'alertname', 'UnknownAlert')
    summary = _value(annotations, 'summary', alert_name)
    runbook_url = _value(annotations, 'runbook_url', '') or _value(annotations, 'runbook', '')

    return CanonicalAlert(
        source_instance_id=source_instance_id,
        source_instance_name=source_instance_name,
        alert_name=alert_name,
        severity=_normalize_severity(_value(labels, 'severity', 'unknown')),
        state=_normalize_state(status=status, ends_at=ends_at),
        starts_at=starts_at,
        ends_at=ends_at,
        labels=labels,
        annotations=annotations,
        receiver=_receiver(alert),
        silenced=bool(silenced_by),
        inhibited=bool(inhibited_by),
        silenced_by=silenced_by,
        inhibited_by=inhibited_by,
        generator_url=str(alert.get('generatorURL') or ''),
        runbook_url=runbook_url,
        fingerprint=str(alert.get('fingerprint') or ''),
        summary=summary,
        description=_value(annotations, 'description', ''),
        duration=human_duration(starts_at, ends_at),
    )


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _value(values: dict[str, Any], key: str, default: str) -> str:
    value = values.get(key, default)
    return default if value is None else str(value)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if item)


def _normalize_severity(value: str) -> str:
    severity = value.lower()
    return severity if severity in {'critical', 'warning', 'info'} else 'unknown'


def _normalize_state(*, status: dict[str, Any], ends_at: Any) -> str:
    raw_state = str(status.get('state') or '').lower()
    if raw_state == 'active':
        return 'firing'
    if raw_state == 'suppressed':
        return 'suppressed'
    if raw_state == 'unprocessed':
        return 'pending'
    if ends_at is not None:
        from datetime import UTC, datetime

        if ends_at <= datetime.now(UTC):
            return 'resolved'
    return raw_state or 'firing'


def _receiver(alert: dict[str, Any]) -> str:
    receivers = alert.get('receivers')
    if not isinstance(receivers, list):
        return '-'
    names = [str(item.get('name')) for item in receivers if isinstance(item, dict) and item.get('name')]
    return ', '.join(names) if names else '-'
