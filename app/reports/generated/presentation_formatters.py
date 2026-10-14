from __future__ import annotations

from datetime import datetime


def _format_report_domain(
    report_domain: str | None,
) -> str:
    labels = {
        'kubernetes': 'KAORI Kubernetes Reports',
        'server': 'KAORI Server Reports',
        'hci': 'KAORI HCI Reports',
    }
    normalized = str(report_domain or 'kubernetes').strip().lower()
    return labels.get(normalized, normalized.replace('_', ' ').title())


def _format_source_badge(
    report_domain: str | None,
    source_kind: str | None,
) -> str:
    normalized_domain = str(report_domain or 'kubernetes').strip().lower()
    if normalized_domain == 'server':
        return 'Server'
    if normalized_domain == 'hci':
        return 'HCI'

    if (source_kind or 'kubernetes') == 'kubernetes':
        return 'Kubernetes'

    return _format_source_kind(source_kind)


def _format_source_kind(
    source_kind: str | None,
) -> str:
    labels = {
        'kubernetes': 'Kubernetes',
        'server': 'Server',
        'vm': 'VM',
        'hci': 'HCI',
    }

    return labels.get(
        source_kind or 'kubernetes',
        (source_kind or 'kubernetes')
        .replace(
            '_',
            ' ',
        )
        .title(),
    )


def _format_period(
    value: str,
) -> str:
    labels = {
        'snapshot': 'Current Inventory Snapshot',
        '24h': 'Last 24 Hours',
        '7d': 'Last 7 Days',
        '30d': 'Last 30 Days',
        '90d': 'Last 90 Days',
        'month': 'This Month',
    }

    return labels.get(
        value,
        value,
    )


def _format_datetime(
    value: datetime | None,
) -> str:
    if value is None:
        return '-'

    return value.strftime(
        '%d %b %Y %H:%M',
    )


def _safe_int(
    value: str,
    default: int,
) -> int:
    try:
        return int(
            value,
        )
    except ValueError:
        return default
