from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def normalize_alertmanager_alerts(
    alerts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized_alerts: list[dict[str, Any]] = []

    for alert in alerts:
        normalized_alerts.append(
            normalize_alertmanager_alert(
                alert,
            )
        )

    return normalized_alerts


def normalize_alertmanager_alert(
    alert: dict[str, Any],
) -> dict[str, Any]:
    labels = safe_dict(
        alert.get(
            'labels',
        )
    )
    annotations = safe_dict(
        alert.get(
            'annotations',
        )
    )
    status = safe_dict(
        alert.get(
            'status',
        )
    )

    starts_at = parse_datetime(
        alert.get(
            'startsAt',
        )
    )
    ends_at = parse_datetime(
        alert.get(
            'endsAt',
        )
    )
    state = normalize_alert_state(
        status=status,
        ends_at=ends_at,
    )

    resource_type, resource_name = detect_resource(
        labels,
    )

    return {
        'alert_name': get_label(
            labels,
            'alertname',
            'UnknownAlert',
        ),
        'severity': normalize_severity(
            get_label(
                labels,
                'severity',
                'unknown',
            )
        ),
        'state': state,
        'namespace': get_label(
            labels,
            'namespace',
            '-',
        ),
        'resource_type': resource_type,
        'resource_name': resource_name,
        'summary': get_annotation(
            annotations,
            'summary',
            get_label(
                labels,
                'alertname',
                'No summary available',
            ),
        ),
        'description': get_annotation(
            annotations,
            'description',
            '',
        ),
        'starts_at': starts_at,
        'ends_at': ends_at,
        'duration': human_duration(
            starts_at,
            ends_at,
        ),
        'source': 'alertmanager',
        'receiver': get_receiver(
            alert,
        ),
        'silenced': bool(
            status.get(
                'silencedBy',
                [],
            )
        ),
        'inhibited': bool(
            status.get(
                'inhibitedBy',
                [],
            )
        ),
        'labels': labels,
        'annotations': annotations,
        'generator_url': str(
            alert.get(
                'generatorURL',
                '',
            )
            or ''
        ),
        'runbook_url': get_annotation(
            annotations,
            'runbook_url',
            '',
        )
        or get_annotation(
            annotations,
            'runbook',
            '',
        ),
        'fingerprint': str(
            alert.get(
                'fingerprint',
                '',
            )
            or ''
        ),
    }


def safe_dict(
    value: Any,
) -> dict[str, Any]:
    if isinstance(
        value,
        dict,
    ):
        return value

    return {}


def get_label(
    labels: dict[str, Any],
    key: str,
    default: str,
) -> str:
    value = labels.get(
        key,
        default,
    )

    if value is None:
        return default

    return str(
        value,
    )


def get_annotation(
    annotations: dict[str, Any],
    key: str,
    default: str,
) -> str:
    value = annotations.get(
        key,
        default,
    )

    if value is None:
        return default

    return str(
        value,
    )


def normalize_severity(
    value: str,
) -> str:
    severity = value.lower()

    if severity in {
        'critical',
        'warning',
        'info',
    }:
        return severity

    return 'unknown'


def normalize_alert_state(
    *,
    status: dict[str, Any],
    ends_at: datetime | None,
) -> str:
    raw_state = str(
        status.get(
            'state',
            '',
        )
    ).lower()

    if raw_state == 'active':
        return 'firing'

    if raw_state == 'suppressed':
        return 'suppressed'

    if raw_state == 'unprocessed':
        return 'pending'

    if ends_at and ends_at <= datetime.now(
        UTC,
    ):
        return 'resolved'

    return raw_state or 'firing'


def detect_resource(
    labels: dict[str, Any],
) -> tuple[str, str]:
    resource_candidates = [
        (
            'node',
            'node',
        ),
        (
            'pod',
            'pod',
        ),
        (
            'deployment',
            'deployment',
        ),
        (
            'statefulset',
            'statefulset',
        ),
        (
            'daemonset',
            'daemonset',
        ),
        (
            'job',
            'job',
        ),
        (
            'persistentvolumeclaim',
            'pvc',
        ),
        (
            'container',
            'container',
        ),
        (
            'service',
            'service',
        ),
        (
            'instance',
            'instance',
        ),
    ]

    for label_key, resource_type in resource_candidates:
        value = labels.get(
            label_key,
        )

        if value:
            return resource_type, str(
                value,
            )

    namespace = labels.get(
        'namespace',
    )

    if namespace:
        return 'namespace', str(
            namespace,
        )

    return 'unknown', '-'


def get_receiver(
    alert: dict[str, Any],
) -> str:
    receivers = alert.get(
        'receivers',
        [],
    )

    if not isinstance(
        receivers,
        list,
    ):
        return '-'

    names: list[str] = []

    for receiver in receivers:
        if not isinstance(
            receiver,
            dict,
        ):
            continue

        name = receiver.get(
            'name',
        )

        if name:
            names.append(
                str(
                    name,
                )
            )

    if not names:
        return '-'

    return ', '.join(
        names,
    )


def parse_datetime(
    value: Any,
) -> datetime | None:
    if not value:
        return None

    if not isinstance(
        value,
        str,
    ):
        return None

    normalized = value.replace(
        'Z',
        '+00:00',
    )

    try:
        parsed = datetime.fromisoformat(
            normalized,
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(
            tzinfo=UTC,
        )

    return parsed.astimezone(
        UTC,
    )


def human_duration(
    starts_at: datetime | None,
    ends_at: datetime | None,
) -> str:
    if starts_at is None:
        return '-'

    end_time = ends_at or datetime.now(
        UTC,
    )

    if end_time <= starts_at:
        end_time = datetime.now(
            UTC,
        )

    total_seconds = int((end_time - starts_at).total_seconds())

    if total_seconds < 60:
        return f'{total_seconds}s'

    total_minutes = total_seconds // 60

    if total_minutes < 60:
        return f'{total_minutes}m'

    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours < 24:
        return f'{hours}h {minutes}m'

    days = hours // 24
    remaining_hours = hours % 24

    return f'{days}d {remaining_hours}h'
