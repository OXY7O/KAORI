from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.alertmanager.service import get_alertmanager_silences
from app.analytics.kubernetes.alerts.contracts import (
    AlertSilenceApiStatus,
    AlertSilenceItem,
    AlertSilenceMatcher,
    AlertSilenceSummary,
    AlertSourceStatus,
    NormalizedAlert,
)
from app.models import Cluster


def load_alertmanager_silences(
    *,
    cluster: Cluster | None,
) -> tuple[list[dict[str, Any]], AlertSilenceApiStatus]:
    if cluster is None:
        return [], {
            'connected': False,
            'error': 'No cluster selected.',
        }

    result = get_alertmanager_silences(
        cluster_id=cluster.id,
    )

    silences = [
        item
        for item in result.get(
            'silences',
            [],
        )
        if isinstance(
            item,
            dict,
        )
    ]

    return silences, {
        'connected': bool(
            result.get(
                'connected',
                False,
            )
        ),
        'error': result.get(
            'error',
        ),
    }


def parse_alertmanager_datetime(
    value: Any,
) -> datetime | None:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
    ):
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace(
                'Z',
                '+00:00',
            )
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


def format_silence_datetime(
    value: Any,
) -> str:
    parsed = parse_alertmanager_datetime(
        value,
    )

    if parsed is None:
        return '-'

    return parsed.strftime(
        '%Y-%m-%d %H:%M UTC',
    )


def normalize_silence_state(
    silence: dict[str, Any],
) -> str:
    status = silence.get(
        'status',
        {},
    )

    if isinstance(
        status,
        dict,
    ):
        state = str(
            status.get(
                'state',
                '',
            )
            or ''
        ).lower()

        if state:
            return state

    now = datetime.now(
        UTC,
    )
    starts_at = parse_alertmanager_datetime(
        silence.get(
            'startsAt',
        )
        or silence.get(
            'starts_at',
        )
    )
    ends_at = parse_alertmanager_datetime(
        silence.get(
            'endsAt',
        )
        or silence.get(
            'ends_at',
        )
    )

    if starts_at is not None and starts_at > now:
        return 'pending'

    if ends_at is not None and ends_at <= now:
        return 'expired'

    return 'active'


def normalize_silence_matchers(
    silence: dict[str, Any],
) -> list[AlertSilenceMatcher]:
    raw_matchers = silence.get(
        'matchers',
        [],
    )

    if not isinstance(
        raw_matchers,
        list,
    ):
        return []

    matchers: list[AlertSilenceMatcher] = []

    for matcher in raw_matchers:
        if not isinstance(
            matcher,
            dict,
        ):
            continue

        name = str(
            matcher.get(
                'name',
                '',
            )
            or ''
        )
        value = str(
            matcher.get(
                'value',
                '',
            )
            or ''
        )

        if not name:
            continue

        matchers.append(
            {
                'name': name,
                'value': value,
                'is_regex': bool(
                    matcher.get(
                        'isRegex',
                        matcher.get(
                            'is_regex',
                            False,
                        ),
                    )
                ),
                'is_equal': bool(
                    matcher.get(
                        'isEqual',
                        matcher.get(
                            'is_equal',
                            True,
                        ),
                    )
                ),
                'label': f'{name}{"=~" if matcher.get("isRegex") else "="}{value}',
            }
        )

    return matchers


def silence_matches_alert(
    *,
    silence: dict[str, Any],
    alert: NormalizedAlert,
) -> bool:
    matchers = normalize_silence_matchers(
        silence,
    )

    if not matchers:
        return False

    labels = alert.get(
        'labels',
        {},
    )

    if not isinstance(
        labels,
        dict,
    ):
        labels = {}

    for matcher in matchers:
        name = str(
            matcher.get(
                'name',
                '',
            )
            or ''
        )
        expected_value = str(
            matcher.get(
                'value',
                '',
            )
            or ''
        )
        actual_value = str(
            labels.get(
                name,
                alert.get(
                    name,
                    '',
                ),
            )
            or ''
        )
        is_equal = bool(
            matcher.get(
                'is_equal',
                True,
            )
        )
        is_regex = bool(
            matcher.get(
                'is_regex',
                False,
            )
        )

        if is_regex:
            try:
                matched = (
                    re.search(
                        expected_value,
                        actual_value,
                    )
                    is not None
                )
            except re.error:
                matched = expected_value in actual_value
        else:
            matched = actual_value == expected_value

        if is_equal and not matched:
            return False

        if not is_equal and matched:
            return False

    return True


def build_silence_summary(
    *,
    cluster: Cluster | None,
    alerts: list[NormalizedAlert],
    source_status: AlertSourceStatus,
) -> AlertSilenceSummary:
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

    if cluster is None:
        return build_empty_silence_summary(
            label='Silence Visibility Unavailable',
            description='Select a cluster before evaluating Alertmanager silences.',
        )

    if resolved_source != 'alertmanager' or not connected:
        return {
            **build_empty_silence_summary(
                label='Silence Visibility Limited',
                description='Silence visibility needs Alertmanager as the active source.',
            ),
            'level': 'limited' if resolved_source == 'metrics_source' and connected else 'unavailable',
            'source': resolved_source,
        }

    silences, silence_status = load_alertmanager_silences(
        cluster=cluster,
    )

    if not silence_status.get(
        'connected',
        False,
    ):
        return {
            **build_empty_silence_summary(
                label='Silence API Unavailable',
                description=str(
                    silence_status.get(
                        'error',
                        'Alertmanager silence API could not be queried.',
                    )
                    or 'Alertmanager silence API could not be queried.'
                ),
            ),
            'level': 'unavailable',
            'source': resolved_source,
        }

    active_items: list[AlertSilenceItem] = []
    pending_count = 0
    expired_count = 0
    silenced_namespaces: set[str] = set()
    silenced_matchers: set[str] = set()
    matched_alert_fingerprints: set[str] = set()

    for silence in silences:
        state = normalize_silence_state(
            silence,
        )
        matchers = normalize_silence_matchers(
            silence,
        )
        matcher_labels = [
            str(
                matcher.get(
                    'label',
                    '',
                )
            )
            for matcher in matchers
            if matcher.get(
                'label',
            )
        ]

        if state == 'pending':
            pending_count += 1
        elif state == 'expired':
            expired_count += 1

        matched_alerts = [
            alert
            for alert in alerts
            if isinstance(
                alert,
                dict,
            )
            and state == 'active'
            and silence_matches_alert(
                silence=silence,
                alert=alert,
            )
        ]

        for matcher in matchers:
            if (
                matcher.get(
                    'name',
                )
                == 'namespace'
            ):
                silenced_namespaces.add(
                    str(
                        matcher.get(
                            'value',
                            '',
                        )
                        or ''
                    )
                )

            if matcher.get(
                'label',
            ):
                silenced_matchers.add(
                    str(
                        matcher.get(
                            'label',
                        )
                    )
                )

        for alert in matched_alerts:
            fingerprint = str(
                alert.get(
                    'fingerprint',
                    '',
                )
                or f'{alert.get("name", "")}/{alert.get("namespace", "")}/{alert.get("target", "")}'
            )

            if fingerprint:
                matched_alert_fingerprints.add(
                    fingerprint,
                )

        if state == 'active':
            active_items.append(
                {
                    'id': str(
                        silence.get(
                            'id',
                            '-',
                        )
                        or '-'
                    ),
                    'state': state,
                    'created_by': str(
                        silence.get(
                            'createdBy',
                            silence.get(
                                'created_by',
                                '-',
                            ),
                        )
                        or '-'
                    ),
                    'comment': str(
                        silence.get(
                            'comment',
                            '-',
                        )
                        or '-'
                    ),
                    'starts_at': format_silence_datetime(
                        silence.get(
                            'startsAt',
                        )
                        or silence.get(
                            'starts_at',
                        )
                    ),
                    'ends_at': format_silence_datetime(
                        silence.get(
                            'endsAt',
                        )
                        or silence.get(
                            'ends_at',
                        )
                    ),
                    'matchers': matcher_labels,
                    'matched_alerts': len(
                        matched_alerts,
                    ),
                }
            )

    active_count = len(
        active_items,
    )

    return {
        'enabled': True,
        'level': 'available',
        'label': 'Alertmanager Silence Context Available',
        'description': ('Active, pending, and expired Alertmanager silences are visible for the selected cluster.'),
        'icon': 'volume-x',
        'source': resolved_source,
        'active_silences': active_count,
        'pending_silences': pending_count,
        'expired_silences': expired_count,
        'matched_alerts': len(
            matched_alert_fingerprints,
        ),
        'silenced_namespaces': sorted(namespace for namespace in silenced_namespaces if namespace)[:6],
        'silenced_matchers': sorted(matcher for matcher in silenced_matchers if matcher)[:8],
        'items': active_items[:5],
    }


def build_empty_silence_summary(
    *,
    label: str = 'Silence Visibility Unavailable',
    description: str = 'Alertmanager silence context is not available.',
) -> AlertSilenceSummary:
    return {
        'enabled': False,
        'level': 'unavailable',
        'label': label,
        'description': description,
        'icon': 'volume-x',
        'source': 'none',
        'active_silences': 0,
        'pending_silences': 0,
        'expired_silences': 0,
        'matched_alerts': 0,
        'silenced_namespaces': [],
        'silenced_matchers': [],
        'items': [],
    }
