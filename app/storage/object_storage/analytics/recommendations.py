from __future__ import annotations

from typing import Any

from app.intelligence.recommendation_alerting import decorate_recommendation_findings
from app.intelligence.service import get_active_recommendation_findings
from app.models.object_storage import ObjectStorageSystem


def empty_recommendation_context() -> dict[str, Any]:
    return {
        'recommendations': [],
        'recommendation_summary': {
            'total': 0,
            'critical': 0,
            'warning': 0,
            'info': 0,
            'highest': 'None',
            'tone': 'normal',
        },
    }


def build_recommendation_context(system: ObjectStorageSystem) -> dict[str, Any]:
    findings = decorate_recommendation_findings(
        get_active_recommendation_findings(domain='object_storage', asset_key=str(system.id))
    )
    critical = sum(str(item.get('severity') or '').lower() == 'critical' for item in findings)
    warning = sum(str(item.get('severity') or '').lower() == 'warning' for item in findings)
    info = max(len(findings) - critical - warning, 0)
    return {
        'recommendations': findings,
        'recommendation_summary': {
            'total': len(findings),
            'critical': critical,
            'warning': warning,
            'info': info,
            'highest': 'Critical' if critical else ('Warning' if warning else ('Info' if info else 'None')),
            'tone': 'critical' if critical else ('warning' if warning else ('info' if info else 'normal')),
        },
    }
