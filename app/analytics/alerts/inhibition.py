from __future__ import annotations

from typing import Any


def build_inhibition_summary(
    *,
    alerts: list[dict[str, Any]],
    source_status: dict[str, Any],
) -> dict[str, Any]:
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

    if resolved_source != 'alertmanager' or not connected:
        return {
            'enabled': False,
            'level': 'limited' if resolved_source == 'prometheus' and connected else 'unavailable',
            'label': 'Inhibition Visibility Limited'
            if resolved_source == 'prometheus' and connected
            else 'Inhibition Visibility Unavailable',
            'description': (
                'Inhibition visibility requires Alertmanager alert lifecycle metadata. '
                'Prometheus fallback does not include inhibitedBy context.'
            ),
            'class': 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300'
            if resolved_source == 'prometheus' and connected
            else 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
            'icon': 'shield-alert',
            'source': resolved_source,
            'rules_detected': 0,
            'matched_alerts': 0,
            'source_equal_labels': [],
            'target_matchers': [],
            'items': [],
        }

    inhibited_alerts: list[dict[str, Any]] = []

    for alert in alerts:
        if not isinstance(
            alert,
            dict,
        ):
            continue

        if bool(
            alert.get(
                'inhibited',
                False,
            )
        ) or bool(
            alert.get(
                'inhibited_by',
                [],
            )
        ):
            inhibited_alerts.append(
                alert,
            )

    source_equal_labels = sorted(
        {
            label
            for alert in inhibited_alerts
            for label in [
                'namespace',
                'alertname',
                'severity',
                'job',
            ]
            if label
            in (
                alert.get(
                    'labels',
                    {},
                )
                if isinstance(
                    alert.get(
                        'labels',
                        {},
                    ),
                    dict,
                )
                else {}
            )
        }
    )

    items = [
        {
            'name': str(
                alert.get(
                    'name',
                    'Unknown Alert',
                )
                or 'Unknown Alert'
            ),
            'namespace': str(
                alert.get(
                    'namespace',
                    '-',
                )
                or '-'
            ),
            'target': str(
                alert.get(
                    'target',
                    '-',
                )
                or '-'
            ),
            'severity': str(
                alert.get(
                    'severity',
                    'none',
                )
                or 'none'
            ),
            'inhibited_by': alert.get(
                'inhibited_by',
                [],
            ),
        }
        for alert in inhibited_alerts[:5]
    ]

    matched_alerts = len(
        inhibited_alerts,
    )

    return {
        'enabled': True,
        'level': 'available',
        'label': 'Alertmanager Inhibition Context Available',
        'description': ('Inhibition visibility is derived from Alertmanager alert lifecycle metadata.'),
        'class': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300',
        'icon': 'shield-alert',
        'source': resolved_source,
        'rules_detected': len(
            {
                str(item)
                for alert in inhibited_alerts
                for item in (
                    alert.get(
                        'inhibited_by',
                        [],
                    )
                    if isinstance(
                        alert.get(
                            'inhibited_by',
                            [],
                        ),
                        list,
                    )
                    else []
                )
            }
        ),
        'matched_alerts': matched_alerts,
        'source_equal_labels': source_equal_labels[:6],
        'target_matchers': [
            'severity',
            'alertname',
            'namespace',
        ]
        if matched_alerts
        else [],
        'items': items,
    }
