from __future__ import annotations

from typing import Any

from app.analytics.alerts.contracts import (
    AlertMissingMetadataItem,
    AlertOwnershipGroup,
    AlertOwnershipSummary,
    AlertRunbookItem,
    AlertSourceStatus,
    NormalizedAlert,
)


def _get_first_string_value(
    mapping: dict[str, Any],
    keys: list[str],
    *,
    default: str = '',
) -> str:
    for key in keys:
        value = mapping.get(
            key,
        )

        if value is None:
            continue

        text = str(
            value,
        ).strip()

        if text:
            return text

    return default


def extract_alert_owner_from_payload(
    *,
    labels: dict[str, Any],
    annotations: dict[str, Any],
    fallback_namespace: Any = '-',
) -> str:
    owner = _get_first_string_value(
        labels,
        [
            'owner',
            'team',
            'service',
            'app',
            'application',
        ],
    )

    if owner:
        return owner

    owner = _get_first_string_value(
        annotations,
        [
            'owner',
            'team',
            'service',
            'app',
            'application',
        ],
    )

    if owner:
        return owner

    namespace = str(
        fallback_namespace or '',
    ).strip()

    if namespace and namespace != '-':
        return namespace

    return '-'


def extract_alert_runbook_from_payload(
    *,
    annotations: dict[str, Any],
) -> str:
    return _get_first_string_value(
        annotations,
        [
            'runbook_url',
            'runbook',
            'runbook_link',
            'runbookURL',
            'dashboard_url',
            'dashboard',
        ],
    )


def extract_alert_contact_from_payload(
    *,
    labels: dict[str, Any],
    annotations: dict[str, Any],
) -> str:
    keys = [
        'contact',
        'contact_point',
        'pager',
        'pagerduty',
        'slack',
        'email',
        'escalation',
    ]

    contact = _get_first_string_value(
        labels,
        keys,
    )

    if contact:
        return contact

    return _get_first_string_value(
        annotations,
        keys,
    )


def get_alert_owner(
    alert: NormalizedAlert,
) -> str:
    explicit_owner = str(
        alert.get(
            'owner',
            '',
        )
        or ''
    ).strip()

    if explicit_owner and explicit_owner != '-':
        return explicit_owner

    labels = alert.get(
        'labels',
        {},
    )

    if not isinstance(
        labels,
        dict,
    ):
        labels = {}

    annotations = alert.get(
        'annotations',
        {},
    )

    if not isinstance(
        annotations,
        dict,
    ):
        annotations = {}

    return extract_alert_owner_from_payload(
        labels=labels,
        annotations=annotations,
        fallback_namespace=alert.get(
            'namespace',
            '-',
        ),
    )


def get_alert_runbook(
    alert: NormalizedAlert,
) -> str:
    explicit_runbook = str(
        alert.get(
            'runbook_url',
            '',
        )
        or ''
    ).strip()

    if explicit_runbook:
        return explicit_runbook

    annotations = alert.get(
        'annotations',
        {},
    )

    if not isinstance(
        annotations,
        dict,
    ):
        annotations = {}

    return extract_alert_runbook_from_payload(
        annotations=annotations,
    )


def get_alert_contact(
    alert: NormalizedAlert,
) -> str:
    explicit_contact = str(
        alert.get(
            'contact',
            '',
        )
        or ''
    ).strip()

    if explicit_contact:
        return explicit_contact

    labels = alert.get(
        'labels',
        {},
    )

    if not isinstance(
        labels,
        dict,
    ):
        labels = {}

    annotations = alert.get(
        'annotations',
        {},
    )

    if not isinstance(
        annotations,
        dict,
    ):
        annotations = {}

    return extract_alert_contact_from_payload(
        labels=labels,
        annotations=annotations,
    )


def build_ownership_summary(
    *,
    alerts: list[NormalizedAlert],
    source_status: AlertSourceStatus,
) -> AlertOwnershipSummary:
    alert_rows = [
        alert
        for alert in alerts
        if isinstance(
            alert,
            dict,
        )
    ]

    total_alerts = len(
        alert_rows,
    )

    if total_alerts == 0:
        return {
            **build_empty_ownership_summary(),
            'label': 'No Alert Metadata Required',
            'description': 'No active alert matched the selected source and filters, so ownership and runbook readiness cannot be evaluated yet.',
            'level': 'unknown',
        }

    owner_groups: dict[str, int] = {}
    runbook_items: list[AlertRunbookItem] = []
    missing_metadata_items: list[AlertMissingMetadataItem] = []
    owner_count = 0
    runbook_count = 0
    contact_count = 0

    for alert in alert_rows:
        owner = get_alert_owner(
            alert,
        )
        runbook = get_alert_runbook(
            alert,
        )
        contact = get_alert_contact(
            alert,
        )

        has_owner = bool(
            owner and owner != '-',
        )
        has_runbook = bool(
            runbook,
        )
        has_contact = bool(
            contact,
        )

        if has_owner:
            owner_count += 1
            owner_groups[owner] = (
                owner_groups.get(
                    owner,
                    0,
                )
                + 1
            )

        if has_runbook:
            runbook_count += 1
            runbook_items.append(
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
                    'url': runbook,
                    'owner': owner if has_owner else '-',
                }
            )

        if has_contact:
            contact_count += 1

        missing_parts: list[str] = []

        if not has_owner:
            missing_parts.append(
                'owner',
            )

        if not has_runbook:
            missing_parts.append(
                'runbook',
            )

        if not has_contact:
            missing_parts.append(
                'contact',
            )

        if missing_parts:
            missing_metadata_items.append(
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
                    'severity': str(
                        alert.get(
                            'severity',
                            'none',
                        )
                        or 'none'
                    ),
                    'missing': missing_parts,
                }
            )

    missing_owner_count = total_alerts - owner_count
    missing_runbook_count = total_alerts - runbook_count
    missing_contact_count = total_alerts - contact_count

    score = round(
        ((owner_count + runbook_count + contact_count) / (total_alerts * 3)) * 100,
    )

    if score >= 85:
        level = 'ready'
        label = 'Ownership Metadata Ready'
        description = 'Most active alerts include owner, runbook, and contact metadata for operational response.'
        icon = 'book-open'
    elif score >= 60:
        level = 'partial'
        label = 'Ownership Metadata Partial'
        description = 'Some alerts have owner or runbook context, but response metadata coverage is not complete.'
        icon = 'clipboard-check'
    elif score >= 30:
        level = 'weak'
        label = 'Ownership Metadata Weak'
        description = 'Many alerts are missing owner, runbook, or contact metadata. Response readiness is weak.'
        icon = 'triangle-alert'
    else:
        level = 'unknown'
        label = 'Ownership Metadata Missing'
        description = 'Most alerts do not include owner, runbook, or contact metadata.'
        icon = 'user-x'

    owner_group_rows: list[AlertOwnershipGroup] = [
        {
            'label': owner,
            'count': count,
            'percent': round(
                (count / total_alerts) * 100,
                1,
            ),
        }
        for owner, count in owner_groups.items()
    ]

    owner_group_rows = sorted(
        owner_group_rows,
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
    )[:6]

    return {
        'score': score,
        'level': level,
        'label': label,
        'description': description,
        'icon': icon,
        'source': str(
            source_status.get(
                'resolved_source',
                'none',
            )
            or 'none'
        ),
        'alert_count': total_alerts,
        'owner_count': owner_count,
        'runbook_count': runbook_count,
        'contact_count': contact_count,
        'missing_owner_count': missing_owner_count,
        'missing_runbook_count': missing_runbook_count,
        'missing_contact_count': missing_contact_count,
        'owner_groups': owner_group_rows,
        'runbook_items': runbook_items[:5],
        'missing_metadata_items': missing_metadata_items[:6],
    }


def build_empty_ownership_summary() -> AlertOwnershipSummary:
    return {
        'score': 0,
        'level': 'unknown',
        'label': 'Ownership Metadata Unknown',
        'description': 'No alert ownership metadata is available yet.',
        'icon': 'search',
        'source': 'none',
        'alert_count': 0,
        'owner_count': 0,
        'runbook_count': 0,
        'contact_count': 0,
        'missing_owner_count': 0,
        'missing_runbook_count': 0,
        'missing_contact_count': 0,
        'owner_groups': [],
        'runbook_items': [],
        'missing_metadata_items': [],
    }
