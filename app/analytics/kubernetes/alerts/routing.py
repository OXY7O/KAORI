from __future__ import annotations

from app.analytics.kubernetes.alerts.contracts import (
    AlertRoutingGroup,
    AlertRoutingSummary,
    AlertSourceStatus,
    NormalizedAlert,
)


def normalize_alert_receiver(
    alert: NormalizedAlert,
) -> str:
    labels = alert.get(
        'labels',
        {},
    )

    if not isinstance(
        labels,
        dict,
    ):
        labels = {}

    receiver = (
        alert.get(
            'receiver',
        )
        or alert.get(
            'route',
        )
        or labels.get(
            'receiver',
        )
        or labels.get(
            'alertmanager_receiver',
        )
        or labels.get(
            'route',
        )
        or labels.get(
            'team',
        )
        or labels.get(
            'owner',
        )
        or 'Receiver Unknown'
    )

    return str(
        receiver or 'Receiver Unknown',
    )


def build_alert_group_key(
    alert: NormalizedAlert,
) -> str:
    labels = alert.get(
        'labels',
        {},
    )

    if not isinstance(
        labels,
        dict,
    ):
        labels = {}

    group_parts = [
        str(
            labels.get(
                'alertname',
                alert.get(
                    'name',
                    'Unknown Alert',
                ),
            )
            or 'Unknown Alert'
        ),
        str(
            labels.get(
                'namespace',
                alert.get(
                    'namespace',
                    '-',
                ),
            )
            or '-'
        ),
        str(
            labels.get(
                'severity',
                alert.get(
                    'severity',
                    'none',
                ),
            )
            or 'none'
        ),
        str(
            labels.get(
                'job',
                labels.get(
                    'service',
                    '-',
                ),
            )
            or '-'
        ),
    ]

    return ' / '.join(
        group_parts,
    )


def build_count_groups(
    alerts: list[NormalizedAlert],
    *,
    key_name: str,
    label_default: str,
    limit: int = 5,
) -> list[AlertRoutingGroup]:
    counts: dict[str, int] = {}

    for alert in alerts:
        if not isinstance(
            alert,
            dict,
        ):
            continue

        value = str(
            alert.get(
                key_name,
                label_default,
            )
            or label_default
        )

        if key_name == 'receiver':
            value = normalize_alert_receiver(
                alert,
            )

        if key_name == 'group_key':
            value = build_alert_group_key(
                alert,
            )

        counts[value] = (
            counts.get(
                value,
                0,
            )
            + 1
        )

    total = sum(
        counts.values(),
    )

    grouped_rows: list[AlertRoutingGroup] = [
        {
            'label': label,
            'count': count,
            'percent': round(
                (count / total) * 100,
                1,
            )
            if total > 0
            else 0,
        }
        for label, count in counts.items()
    ]

    return sorted(
        grouped_rows,
        key=lambda item: (
            item.get(
                'count',
                0,
            ),
            item.get(
                'label',
                '',
            ),
        ),
        reverse=True,
    )[:limit]


def build_routing_summary(
    *,
    alerts: list[NormalizedAlert],
    source_status: AlertSourceStatus,
) -> AlertRoutingSummary:
    resolved_source = str(
        source_status.get(
            'resolved_source',
            'none',
        )
        or 'none'
    )
    connected = bool(
        source_status.get(
            'connected',
            False,
        )
    )

    alert_rows = [
        alert
        for alert in alerts
        if isinstance(
            alert,
            dict,
        )
    ]

    receiver_groups = build_count_groups(
        alert_rows,
        key_name='receiver',
        label_default='Receiver Unknown',
    )
    severity_groups = build_count_groups(
        alert_rows,
        key_name='severity',
        label_default='none',
    )
    namespace_groups = build_count_groups(
        alert_rows,
        key_name='namespace',
        label_default='-',
    )
    grouping_keys = build_count_groups(
        alert_rows,
        key_name='group_key',
        label_default='Unknown Alert / - / none / -',
    )

    receiver_count = len(
        {
            normalize_alert_receiver(
                alert,
            )
            for alert in alert_rows
        }
    )
    group_count = len(
        {
            build_alert_group_key(
                alert,
            )
            for alert in alert_rows
        }
    )
    fingerprint_count = sum(
        1
        for alert in alert_rows
        if str(
            alert.get(
                'fingerprint',
                '',
            )
            or ''
        )
    )
    namespace_count = len(
        {
            str(
                alert.get(
                    'namespace',
                    '',
                )
                or ''
            )
            for alert in alert_rows
            if str(
                alert.get(
                    'namespace',
                    '',
                )
                or ''
            )
            and str(
                alert.get(
                    'namespace',
                    '',
                )
                or ''
            )
            != '-'
        }
    )

    if resolved_source == 'alertmanager' and connected:
        enabled = True
        level = 'available'
        label = 'Alertmanager Routing Context Available'
        description = 'Alertmanager context is available.'
        icon = 'route'
    elif resolved_source == 'prometheus' and connected:
        enabled = False
        level = 'limited'
        label = 'Routing Context Limited'
        description = 'Prometheus fallback is active; Alertmanager context is limited.'
        icon = 'activity'
    else:
        enabled = False
        level = 'unavailable'
        label = 'Routing Context Unavailable'
        description = 'Alert routing cannot be evaluated because no alert source is currently connected.'
        icon = 'circle-alert'

    return {
        'enabled': enabled,
        'level': level,
        'label': label,
        'description': description,
        'icon': icon,
        'source': resolved_source,
        'alert_count': len(
            alert_rows,
        ),
        'receiver_count': receiver_count,
        'group_count': group_count,
        'fingerprint_count': fingerprint_count,
        'namespace_count': namespace_count,
        'severity_groups': severity_groups,
        'receiver_groups': receiver_groups,
        'namespace_groups': namespace_groups,
        'grouping_keys': grouping_keys,
    }


def build_empty_routing_summary() -> AlertRoutingSummary:
    return {
        'enabled': False,
        'level': 'unavailable',
        'label': 'Routing Context Unavailable',
        'description': 'Alert routing cannot be evaluated because no alert source is currently connected.',
        'icon': 'circle-off',
        'source': 'none',
        'alert_count': 0,
        'receiver_count': 0,
        'group_count': 0,
        'fingerprint_count': 0,
        'namespace_count': 0,
        'severity_groups': [],
        'receiver_groups': [],
        'namespace_groups': [],
        'grouping_keys': [],
    }
