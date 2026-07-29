from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_TONE_MAP = {
    'green': 'normal',
    'normal': 'normal',
    'blue': 'info',
    'purple': 'info',
    'info': 'info',
    'amber': 'warning',
    'warning': 'warning',
    'red': 'critical',
    'critical': 'critical',
    'gray': 'unknown',
    'slate': 'unknown',
    'unknown': 'unknown',
}

_DOMAIN_ICONS = {
    'kubernetes': 'boxes',
    'server': 'server-cog',
    'hci': 'network',
}

_RELATED_INFORMATION = [
    {
        'label': 'Generate Report',
        'description': 'Select a report type, scope, period, sections, and output contract.',
        'icon': 'plus-circle',
        'href': '/reports/generate',
    },
    {
        'label': 'Report Templates',
        'description': 'Review protected base templates and create reusable custom templates.',
        'icon': 'layout-template',
        'href': '/reports/templates',
    },
    {
        'label': 'Report Schedules',
        'description': 'Create recurring generation definitions and run schedules on demand.',
        'icon': 'calendar-clock',
        'href': '/reports/schedules',
    },
    {
        'label': 'Report Storage',
        'description': 'Review the active artifact backend, retention boundary, and storage health.',
        'icon': 'hard-drive',
        'href': '/reports/storage',
    },
    {
        'label': 'Infrastructure Integrations',
        'description': 'Manage the provider connections that determine report data availability.',
        'icon': 'plug-zap',
        'href': '/integrations/',
    },
]


def normalize_reports_overview_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the complete presentation contract required by Reports Overview.

    The normalizer accepts both the redesigned payload and the previous Reports Overview
    payload. This prevents template failures during rolling or partial deployments where
    templates reload before the long-running Flask process reloads the Python service.
    """

    normalized = dict(payload or {})

    coverage = _normalize_report_type_coverage(normalized.get('report_type_coverage'))
    normalized['report_type_coverage'] = coverage
    if not normalized.get('report_type_summary'):
        normalized['report_type_summary'] = _build_report_type_summary(coverage)

    pipeline_status = _normalize_status_items(normalized.get('pipeline_status'))
    normalized['pipeline_status'] = pipeline_status
    if not normalized.get('pipeline_summary'):
        normalized['pipeline_summary'] = _build_pipeline_summary(pipeline_status)

    current_status = _normalize_status_items(normalized.get('current_status'))
    normalized['current_status'] = current_status
    if not normalized.get('current_status_summary'):
        normalized['current_status_summary'] = _build_current_status_summary(current_status)

    normalized['reporting_context'] = _normalize_reporting_context(normalized.get('reporting_context'))
    normalized['reporting_operating_model'] = _normalize_operating_model(
        normalized.get('reporting_operating_model')
    )
    normalized['data_collection_status'] = _normalize_data_collection_status(
        normalized.get('data_collection_status')
    )

    if not normalized.get('related_information'):
        normalized['related_information'] = [dict(item) for item in _RELATED_INFORMATION]

    normalized.setdefault('page_title', 'Reports Overview')
    normalized.setdefault(
        'page_subtitle',
        'Generate governed infrastructure reports from connected KAORI data sources.',
    )
    normalized.setdefault('selected_cluster_label', 'All Infrastructure Scopes')
    normalized.setdefault('report_engine_status', 'Ready')
    normalized.setdefault('storage_status', 'Storage Review')
    normalized['summary_cards'] = _normalize_summary_cards(normalized.get('summary_cards'))
    normalized.setdefault('recent_reports', [])

    return normalized



def _normalize_summary_cards(raw: Any) -> list[dict[str, Any]]:
    defaults = [
        {
            'label': 'Total Reports',
            'value': '0',
            'caption': 'All Report Records',
            'icon': 'files',
            'tone': 'blue',
        },
        {
            'label': 'Generated This Month',
            'value': '0',
            'caption': 'Reports Created This Month',
            'icon': 'calendar-days',
            'tone': 'green',
        },
        {
            'label': 'Ready Reports',
            'value': '0',
            'caption': 'Available for Download',
            'icon': 'check-circle-2',
            'tone': 'purple',
        },
        {
            'label': 'Enabled Schedules',
            'value': '0',
            'caption': 'Enabled Recurring Definitions',
            'icon': 'calendar-clock',
            'tone': 'purple',
        },
    ]
    if not isinstance(raw, list):
        return defaults

    cards = [dict(card) for card in raw if isinstance(card, Mapping)]
    while len(cards) < len(defaults):
        cards.append(dict(defaults[len(cards)]))
    return cards

def _normalize_report_type_coverage(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {'domains': [], 'available_count': 0, 'total_count': 0}

    if isinstance(raw.get('domains'), list):
        domains = [_normalize_domain(item) for item in raw.get('domains', []) if isinstance(item, Mapping)]
    else:
        domains = []
        for key, value in raw.items():
            if not isinstance(value, Mapping):
                continue
            domain = dict(value)
            domain.setdefault('key', str(key))
            domain.setdefault('icon', _DOMAIN_ICONS.get(str(key), 'file-text'))
            domains.append(_normalize_domain(domain))

    return {
        'domains': domains,
        'available_count': sum(int(domain.get('available_count', 0)) for domain in domains),
        'total_count': sum(int(domain.get('total_count', 0)) for domain in domains),
    }


def _normalize_domain(raw: Mapping[str, Any]) -> dict[str, Any]:
    key = str(raw.get('key', 'report'))
    items = []
    for item in raw.get('items', []) if isinstance(raw.get('items'), list) else []:
        if not isinstance(item, Mapping):
            continue
        status = str(item.get('status', 'Reserved'))
        items.append(
            {
                **dict(item),
                'status': status,
                'tone': _status_tone(status, item.get('tone')),
                'icon': str(item.get('icon', 'file-text')),
                'name': str(item.get('name', 'Report Type')),
                'description': str(item.get('description', 'Report contract.')),
            }
        )

    available_count = int(raw.get('available_count', 0) or 0)
    total_count = int(raw.get('total_count', len(items)) or len(items))
    status = str(raw.get('status') or ('Available' if available_count else 'Reserved'))

    return {
        **dict(raw),
        'key': key,
        'label': str(raw.get('label', key.replace('_', ' ').title())),
        'description': str(raw.get('description', 'Infrastructure report contracts.')),
        'icon': str(raw.get('icon', _DOMAIN_ICONS.get(key, 'file-text'))),
        'status': status,
        'tone': _status_tone(status, raw.get('tone')),
        'items': items,
        'available_count': available_count,
        'total_count': total_count,
    }


def _build_report_type_summary(coverage: Mapping[str, Any]) -> dict[str, str]:
    available = int(coverage.get('available_count', 0) or 0)
    total = int(coverage.get('total_count', 0) or 0)
    return {
        'available': str(available),
        'total': str(total),
        'label': f'{available} Available Types',
        'description': f'{total} report contracts across connected and planned infrastructure domains.',
    }


def _normalize_status_items(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    items: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        status = str(item.get('status', item.get('value', 'Unknown')))
        items.append(
            {
                **dict(item),
                'tone': _status_tone(status, item.get('tone')),
                'icon': str(item.get('icon', 'info')),
            }
        )
    return items


def _build_pipeline_summary(items: list[dict[str, Any]]) -> dict[str, int]:
    return {
        'ready': sum(1 for item in items if item.get('tone') == 'normal'),
        'review': sum(1 for item in items if item.get('tone') in {'warning', 'critical'}),
        'planned': sum(1 for item in items if item.get('tone') in {'info', 'unknown'}),
        'total': len(items),
    }


def _build_current_status_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    ready = sum(1 for item in items if item.get('tone') == 'normal')
    review = sum(1 for item in items if item.get('tone') in {'warning', 'critical'})
    neutral = sum(1 for item in items if item.get('tone') in {'info', 'unknown'})
    return {
        'ready': ready,
        'review': review,
        'neutral': neutral,
        'posture': 'Needs Review' if review else 'Ready',
        'tone': 'warning' if review else 'normal',
    }


def _normalize_reporting_context(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        bullets = item.get('bullets') if isinstance(item.get('bullets'), list) else []
        detail = item.get('detail') or ' '.join(str(value) for value in bullets if value)
        normalized.append(
            {
                **dict(item),
                'title': str(item.get('title', 'Reporting Context')),
                'description': str(item.get('description', 'Reporting context is available.')),
                'detail': str(detail or 'Review the connected integrations and report contract.'),
                'icon': str(item.get('icon', 'info')),
            }
        )
    return normalized


def _normalize_operating_model(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {
            'title': 'Reporting Operating Model',
            'description': 'How KAORI composes, governs, stores, and automates infrastructure reports.',
            'cards': [],
        }

    cards = _normalize_status_items(raw.get('cards'))
    return {
        **dict(raw),
        'title': str(raw.get('title', 'Reporting Operating Model')),
        'description': str(
            raw.get(
                'description',
                'How KAORI composes, governs, stores, and automates infrastructure reports.',
            )
        ),
        'cards': cards,
    }


def _normalize_data_collection_status(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue

        if item.get('stage'):
            status = str(item.get('status', 'Unknown'))
            normalized.append(
                {
                    **dict(item),
                    'stage': str(item.get('stage')),
                    'stage_label': str(item.get('stage_label', str(item.get('stage')).title())),
                    'name': str(item.get('name', 'Infrastructure Integration')),
                    'category': str(item.get('category', 'Infrastructure Source')),
                    'status': status,
                    'tone': _status_tone(status, item.get('tone')),
                    'icon': str(item.get('icon', 'database-zap')),
                    'description': str(item.get('description', 'Integration readiness information.')),
                }
            )
            continue

        status = str(item.get('status', 'Reserved'))
        tone = _status_tone(status, item.get('tone'))
        stage = 'ready' if tone == 'normal' else 'reserved' if tone == 'unknown' else 'planned'
        details = item.get('items') if isinstance(item.get('items'), list) else []
        normalized.append(
            {
                'stage': stage,
                'stage_label': 'Ready Now' if stage == 'ready' else stage.title(),
                'name': str(item.get('title', item.get('name', 'Infrastructure Integration'))),
                'category': 'Infrastructure Source',
                'status': status,
                'tone': tone,
                'icon': str(item.get('icon', 'database-zap')),
                'description': ' '.join(str(value) for value in details if value)
                or str(item.get('description', 'Integration readiness information.')),
            }
        )

    return normalized


def _status_tone(status: str, tone: Any) -> str:
    normalized_status = status.strip().lower()
    if normalized_status in {'ready', 'available', 'selected', 'healthy'}:
        return 'normal'
    if normalized_status in {'failed', 'critical', 'unavailable'}:
        return 'critical'
    if normalized_status in {'review', 'needs review', 'warning', 'path review'}:
        return 'warning'
    if normalized_status in {'planned', 'coming soon'}:
        return 'info'
    if normalized_status in {'reserved', 'unknown', 'not configured'}:
        return 'unknown'
    return _TONE_MAP.get(str(tone or '').strip().lower(), 'unknown')
