from __future__ import annotations

from typing import Any

from app.intelligence.recommendation_alerting import decorate_recommendation_findings
from app.intelligence.service import get_active_recommendation_findings
from app.models.object_storage import ObjectStorageSystem

_CONTEXT_LABELS = {
    'overview': 'Overview',
    'capacity': 'Capacity & Usage',
    'performance': 'Performance',
    'forecast': 'Forecast',
    'top_consumers': 'Top Consumers',
    'alerts': 'Alerts & Anomalies',
}


def empty_recommendation_context() -> dict[str, Any]:
    return {
        'recommendations': [],
        'recommendation_context_key': 'overview',
        'recommendation_context_label': 'Overview',
        'recommendation_summary': {
            'total': 0,
            'critical': 0,
            'warning': 0,
            'info': 0,
            'highest': 'None',
            'tone': 'normal',
        },
    }


def _matches_page_context(item: dict[str, Any], page_key: str) -> bool:
    if page_key == 'overview':
        return True

    base_rule_key = str(item.get('base_rule_key') or item.get('rule_key') or '').split(':', 1)[0]
    category = str(item.get('category') or '').strip().lower()
    source_kind = str(item.get('source_kind') or '').strip().lower()

    if page_key == 'capacity':
        return category == 'capacity'
    if page_key == 'performance':
        return category in {'performance', 'reliability'}
    if page_key == 'forecast':
        return base_rule_key.startswith('object_storage.forecast.')
    if page_key == 'top_consumers':
        return source_kind == 'object_storage_bucket'
    if page_key == 'alerts':
        return base_rule_key.startswith('object_storage.metric.')
    return True


def build_recommendation_context(system: ObjectStorageSystem, *, page_key: str) -> dict[str, Any]:
    normalized_page = page_key if page_key in _CONTEXT_LABELS else 'overview'
    findings = decorate_recommendation_findings(
        get_active_recommendation_findings(domain='object_storage', asset_key=str(system.id))
    )
    findings = [item for item in findings if _matches_page_context(item, normalized_page)]
    critical = sum(str(item.get('severity') or '').lower() == 'critical' for item in findings)
    warning = sum(str(item.get('severity') or '').lower() == 'warning' for item in findings)
    info = max(len(findings) - critical - warning, 0)
    return {
        'recommendations': findings,
        'recommendation_context_key': normalized_page,
        'recommendation_context_label': _CONTEXT_LABELS[normalized_page],
        'recommendation_summary': {
            'total': len(findings),
            'critical': critical,
            'warning': warning,
            'info': info,
            'highest': 'Critical' if critical else ('Warning' if warning else ('Info' if info else 'None')),
            'tone': 'critical' if critical else ('warning' if warning else ('info' if info else 'normal')),
        },
    }
