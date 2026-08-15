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
    normalized['reporting_operating_model'] = _normalize_operating_model(normalized.get('reporting_operating_model'))
    normalized['data_collection_status'] = _normalize_data_collection_status(normalized.get('data_collection_status'))

    if not normalized.get('related_information'):
        normalized['related_information'] = [dict(item) for item in _RELATED_INFORMATION]

    normalized.setdefault('page_title', 'Reports Overview')
    normalized.setdefault(
        'page_subtitle',
        'Generate, schedule, retain, and audit governed reporting artifacts across connected infrastructure scopes with clear readiness, storage, and lifecycle context.',
    )
    normalized.setdefault('selected_cluster_label', 'All Infrastructure Scopes')
    normalized.setdefault('report_engine_status', 'Ready')
    normalized.setdefault('storage_status', 'Storage Review')
    normalized['summary_cards'] = _normalize_summary_cards(normalized.get('summary_cards'))
    normalized['reporting_operations'] = _normalize_reporting_operations(
        normalized.get('reporting_operations'), normalized
    )
    normalized['reporting_coverage'] = _normalize_reporting_coverage(normalized.get('reporting_coverage'))
    normalized['artifact_statistics'] = _normalize_artifact_statistics(normalized.get('artifact_statistics'))
    normalized['artifact_portfolio'] = _normalize_artifact_portfolio(normalized.get('artifact_portfolio'))
    normalized['automation_summary'] = _normalize_automation_summary(normalized.get('automation_summary'))

    return normalized


def _normalize_summary_cards(raw: Any) -> list[dict[str, Any]]:
    defaults = [
        {
            'label': 'Generated',
            'value': '0',
            'caption': 'Ready or archived artifacts',
            'icon': 'files',
            'tone': 'info',
        },
        {
            'label': 'Ready',
            'value': '0',
            'caption': 'Available artifacts',
            'icon': 'circle-check',
            'tone': 'normal',
        },
        {
            'label': 'In Progress',
            'value': '0',
            'caption': 'Requested or generating',
            'icon': 'loader-circle',
            'tone': 'info',
        },
        {
            'label': 'Failed',
            'value': '0',
            'caption': 'Requires review',
            'icon': 'triangle-alert',
            'tone': 'normal',
        },
    ]
    if not isinstance(raw, list):
        return defaults

    cards = [dict(card) for card in raw if isinstance(card, Mapping)]
    if not cards:
        return defaults

    # Older workers may still emit the previous four summary labels during a rolling deploy.
    label_map = {str(card.get('label', '')): card for card in cards}
    if 'Generated' not in label_map and 'Total Reports' in label_map:
        return defaults

    while len(cards) < len(defaults):
        cards.append(dict(defaults[len(cards)]))
    return cards[:4]


def _normalize_reporting_operations(raw: Any, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        items = [dict(item) for item in raw if isinstance(item, Mapping)]
        if items:
            return items[:3]

    raw_worker = payload.get('worker_context')
    raw_storage = payload.get('storage_context')
    worker = raw_worker if isinstance(raw_worker, Mapping) else {}
    storage = raw_storage if isinstance(raw_storage, Mapping) else {}
    return [
        {
            'label': 'Generation Queue',
            'value': str(worker.get('label', 'Review')),
            'status': str(worker.get('label', 'Unknown')),
            'tone': str(worker.get('tone', 'unknown')),
            'icon': 'workflow',
            'caption': str(worker.get('description', 'Reports queue readiness is unavailable.')),
            'action_label': 'Generate Report',
            'href': '/reports/generate',
        },
        {
            'label': 'Active Schedules',
            'value': '0',
            'status': 'Review',
            'tone': 'unknown',
            'icon': 'calendar-clock',
            'caption': 'Open Schedules to review recurring definitions.',
            'action_label': 'Open Schedules',
            'href': '/reports/schedules',
        },
        {
            'label': 'Artifact Storage',
            'value': str(storage.get('label', 'Report Storage')),
            'status': str(storage.get('display_status', 'Review')),
            'tone': 'normal' if str(storage.get('status')) == 'selected' else 'warning',
            'icon': 'hard-drive',
            'caption': str(storage.get('active_detail', 'Configured report artifact backend.')).capitalize(),
            'action_label': 'Open Storage',
            'href': '/reports/storage',
        },
    ]


def _normalize_reporting_coverage(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        groups = [dict(item) for item in raw if isinstance(item, Mapping)]
        if groups:
            for group in groups:
                raw_items = group.get('items')
                items = raw_items if isinstance(raw_items, list) else []
                group.setdefault('contract_count', len(items))
            return groups[:2]

    return [
        {
            'key': 'analytics',
            'label': 'Analytics Reports',
            'description': 'Time-range analysis and operational evidence.',
            'icon': 'chart-no-axes-combined',
            'formats': ['PDF', 'CSV'],
            'items': [],
            'contract_count': 0,
        },
        {
            'key': 'inventory',
            'label': 'Inventory Reports',
            'description': 'Point-in-time Kubernetes asset evidence.',
            'icon': 'boxes',
            'formats': ['XLSX', 'CSV'],
            'items': [],
            'contract_count': 0,
        },
    ]


def _normalize_artifact_statistics(raw: Any) -> list[dict[str, Any]]:
    defaults = [
        {
            'label': 'Requests This Month',
            'value': '0',
            'caption': 'Report requests created this calendar month',
            'icon': 'calendar-range',
        },
        {
            'label': 'Completion Rate',
            'value': '—',
            'caption': 'Ready or archived among resolved requests',
            'icon': 'badge-check',
        },
        {
            'label': 'Artifact Footprint',
            'value': '0 B',
            'caption': 'Stored ready and archived artifacts',
            'icon': 'database',
        },
        {
            'label': 'Custom Templates',
            'value': '0',
            'caption': 'Reusable operator-defined templates',
            'icon': 'layout-template',
        },
    ]
    if not isinstance(raw, list):
        return defaults
    items = [dict(item) for item in raw if isinstance(item, Mapping)]
    return (items + defaults[len(items) :])[:4]


def _normalize_artifact_portfolio(raw: Any) -> dict[str, list[dict[str, str]]]:
    if isinstance(raw, Mapping):
        raw_families = raw.get('families')
        raw_formats = raw.get('formats')
        families = (
            [dict(item) for item in raw_families if isinstance(item, Mapping)] if isinstance(raw_families, list) else []
        )
        formats = (
            [dict(item) for item in raw_formats if isinstance(item, Mapping)] if isinstance(raw_formats, list) else []
        )
        if families and formats:
            return {'families': families, 'formats': formats}
    return {
        'families': [
            {'label': 'Analytics', 'value': '0', 'icon': 'chart-no-axes-combined'},
            {'label': 'Inventory', 'value': '0', 'icon': 'boxes'},
        ],
        'formats': [
            {'label': 'PDF', 'value': '0'},
            {'label': 'CSV', 'value': '0'},
            {'label': 'XLSX', 'value': '0'},
        ],
    }


def _normalize_automation_summary(raw: Any) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        raw = {}
    return {
        'active_schedules': str(raw.get('active_schedules', '0')),
        'total_schedules': str(raw.get('total_schedules', '0')),
        'custom_templates': str(raw.get('custom_templates', '0')),
        'available_contracts': str(raw.get('available_contracts', '0')),
    }


def _normalize_report_type_coverage(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {'domains': [], 'available_count': 0, 'total_count': 0}

    raw_domains = raw.get('domains')
    if isinstance(raw_domains, list):
        domains = [_normalize_domain(item) for item in raw_domains if isinstance(item, Mapping)]
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
    raw_items = raw.get('items')
    for item in raw_items if isinstance(raw_items, list) else []:
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
        raw_bullets = item.get('bullets')
        bullets = raw_bullets if isinstance(raw_bullets, list) else []
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
        raw_details = item.get('items')
        details = raw_details if isinstance(raw_details, list) else []
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
