from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f'FAIL — KAORI Operational Data Semantics · {message}')


def main() -> None:
    os_analytics = _read('app/storage/object_storage/analytics/recommendations.py')
    os_dashboard = _read('app/storage/object_storage/dashboard/service.py')
    overview = _read('app/templates/storage/object_storage/analytics/partials/_overview_workspace.html')

    _require(
        'get_active_recommendation_findings' not in os_analytics,
        'Object Storage Analytics recommendations must be page-local evidence guidance, not central Intelligence findings.',
    )
    _require(
        'get_dashboard_recommendation_findings' in os_dashboard,
        'Object Storage Dashboard Recommended Actions must consume central Intelligence recommendations.',
    )
    _require(
        "('alerts', 'Alerts', 'bell-ring')" in overview,
        'Object Storage Analytics Overview must expose Alerts rather than a generic Recommendations tab.',
    )
    _require(
        "('recommendations', 'Recommendations'" not in overview,
        'Object Storage Analytics Overview must not own contextual recommendations.',
    )

    inventory_roots = (
        'app/kubernetes/inventory',
        'app/storage/object_storage/inventory',
        'app/templates/kubernetes/inventory',
        'app/templates/storage/object_storage/inventory',
    )
    inventory_source = '\n'.join(
        path.read_text(encoding='utf-8')
        for relative in inventory_roots
        for path in (ROOT / relative).rglob('*')
        if path.suffix in {'.py', '.html'}
    )
    for token in (
        'get_active_recommendation_findings',
        'get_dashboard_recommendation_findings',
        'intelligence.recommendation_details',
        'alert_intelligence.index',
        'Alert Intelligence',
        'Recommended Actions',
    ):
        _require(token not in inventory_source, f'Inventory must remain factual asset truth; found ownership token: {token}.')

    for relative in (
        'app/templates/kubernetes/dashboard/partials/_alerts_summary.html',
        'app/templates/storage/object_storage/dashboard/partials/_alerts_summary.html',
    ):
        source = _read(relative)
        _require('Alert Intelligence' in source, f'{relative} must identify Alert Intelligence as the Dashboard source.')
        _require('KAORI Alert Cases Available' in source, f'{relative} must expose canonical AlertCase availability.')
        _require('KAORI Alert Intelligence' in source, f'{relative} must expose canonical Alert Intelligence provenance.')
        _require('Top 3 Cases' not in source, f'{relative} must not use domain-specific Top N metadata.')

    print('PASS — KAORI Operational Data Semantics · Inventory/Dashboard/Analytics/Intelligence authority boundaries')


if __name__ == '__main__':
    main()
