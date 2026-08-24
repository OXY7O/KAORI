from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KUBERNETES = ROOT / 'app' / 'templates' / 'kubernetes' / 'dashboard'
OBJECT_STORAGE = ROOT / 'app' / 'templates' / 'storage' / 'object_storage' / 'dashboard'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def combined(root: Path) -> str:
    return '\n'.join(path.read_text(encoding='utf-8') for path in sorted(root.rglob('*.html')))


def test_operational_dashboards_share_the_same_outer_workspace_grammar() -> None:
    kubernetes = read('app/templates/kubernetes/dashboard/partials/_content.html')
    object_storage = read('app/templates/storage/object_storage/dashboard/partials/_content.html')

    for source in (kubernetes, object_storage):
        assert 'components/workspace_tabs.html' in source
        assert "('overview', 'Operations Overview', 'activity')" in source
        assert "('capacity', 'Capacity & Demand', 'gauge')" in source
        assert "('signals', 'Signals & Actions', 'bell-ring')" in source
        assert "('reporting', 'Reporting', 'file-text')" in source
        assert 'moveTab(currentTab, direction, prefix)' in source
        assert "url.searchParams.set('tab', tab)" in source
        assert "window.history.replaceState({}, '', url)" in source
        assert 'hx-trigger="revealed"' in source

    assert 'kubernetes/dashboard/partials/_hero.html' in kubernetes
    assert 'kubernetes/dashboard/partials/_signal_overview.html' in kubernetes
    assert 'storage/object_storage/dashboard/partials/_hero.html' in object_storage
    assert 'storage/object_storage/dashboard/partials/_signal_overview.html' in object_storage
    assert 'class="mt-5 space-y-5"' in kubernetes
    assert 'class="mt-5 space-y-5"' in object_storage


def test_operational_dashboards_share_peer_grid_and_reporting_proportions() -> None:
    kubernetes = combined(KUBERNETES)
    object_storage = combined(OBJECT_STORAGE)

    for source in (kubernetes, object_storage):
        assert source.count('peer_content_grid.layout_classes()') >= 4
        assert "column_classes('primary', 'seven-five')" in source
        assert "column_classes('secondary', 'seven-five')" in source
        assert 'Controlled Reporting Flow' in source
        assert 'Controlled Response Flow' in source


def test_operational_dashboard_family_uses_canonical_palette_and_typography() -> None:
    arbitrary_text = re.compile(r'\btext-\[[^\]]+\]')
    arbitrary_tracking = re.compile(r'\btracking-\[[^\]]+\]')
    local_color = re.compile(r'(?:bg|text|border)-\[#[0-9A-Fa-f]{3,8}\]')

    for root in (KUBERNETES, OBJECT_STORAGE):
        for path in sorted(root.rglob('*.html')):
            source = path.read_text(encoding='utf-8')
            assert arbitrary_text.search(source) is None, path
            assert arbitrary_tracking.search(source) is None, path
            assert local_color.search(source) is None, path
            assert 'font-extrabold' not in source, path


def test_generic_summary_explanation_is_retired_from_operational_dashboards() -> None:
    assert 'What This Summary Means' not in combined(KUBERNETES)
    assert 'What This Summary Means' not in combined(OBJECT_STORAGE)


def test_dashboard_copy_is_compact_and_snapshot_safe() -> None:
    freshness = read('app/kubernetes/dashboard/sections/freshness.py')
    capacity = read('app/kubernetes/dashboard/sections/capacity.py')
    kubernetes_capacity = read('app/templates/kubernetes/dashboard/partials/_capacity_snapshot.html')
    kubernetes_alerts = read('app/templates/kubernetes/dashboard/partials/_alerts_summary.html')
    kubernetes_reporting = read('app/templates/kubernetes/dashboard/partials/_reporting_guidance.html')
    object_capacity = read('app/templates/storage/object_storage/dashboard/partials/_capacity.html')
    object_alert_guidance = read(
        'app/templates/storage/object_storage/dashboard/partials/_alert_response_guidance.html'
    )
    object_reporting = read('app/templates/storage/object_storage/dashboard/partials/_reporting_guidance.html')
    object_summary = read('app/templates/storage/object_storage/dashboard/partials/_reporting_summary.html')

    assert 'Committed analytics available' in freshness
    assert 'Generated reports are retained artifacts, separate from current Kubernetes health.' in freshness
    assert 'No immediate scaling required.' in capacity
    assert 'Worker-node CPU, memory, and pod headroom; control-plane nodes excluded.' in kubernetes_capacity
    assert 'Apply the approved capacity/workload change' in kubernetes_capacity
    assert 'KAORI Alert Intelligence case evidence is temporarily unavailable.' in kubernetes_alerts
    assert 'Validate reporting activity and follow the governed KAORI workflow.' in kubernetes_reporting
    assert 'Validate reporting activity and follow the governed KAORI workflow.' in object_reporting
    assert "operational_callout.render('Reporting Control'" in kubernetes_reporting
    assert "operational_callout.render('Reporting Control'" in object_reporting
    assert kubernetes_reporting.index('Reporting Control') < kubernetes_reporting.index('Controlled Reporting Flow')
    assert object_reporting.index('Reporting Control') < object_reporting.index('Controlled Reporting Flow')
    assert 'Committed capacity, usage, headroom, and response path.' in object_capacity
    assert (
        'Capacity uses the committed Object Storage Analytics snapshot; no live provider query is issued.'
        in object_capacity
    )
    assert (
        'Developing capacity, request-path, or availability risk. Investigate before escalation.'
        in object_alert_guidance
    )
    assert 'Low-risk operational signal. Validate relevance, recurrence, and scope.' in object_alert_guidance
    assert 'Object Storage report output, definitions, schedules, and recent generation activity.' in object_summary

    forbidden = (
        'Committed analytics snapshot available',
        'Generated reports are retained operational artifacts, separate from current Kubernetes health signals.',
        'Worker-node CPU, memory, and pod headroom. Control-plane nodes are excluded.',
        'Apply the approved capacity or workload adjustment',
        'Apply the approved capacity or workload change',
        'Alert collection is temporarily unavailable.',
        'Alert collection is unavailable. KAORI retains configured integrations and retries automatically.',
        'continue through the controlled KAORI reporting workflow',
        'Committed usable capacity, usage, headroom, and the controlled response path',
        'Committed capacity, usage, headroom, and response path for the selected Object Storage system.',
        (
            'Capacity values come from the committed Object Storage Analytics snapshot. '
            'Dashboard rendering does not issue live provider queries.'
        ),
        'Capacity, request-path, or availability risk is developing. Investigate before escalation.',
        'Operational context or low-risk signal. Validate relevance, recurrence, and affected scope.',
        'Object Storage report output, reusable definitions',
    )
    all_source = '\n'.join(
        (
            freshness,
            capacity,
            kubernetes_capacity,
            kubernetes_alerts,
            kubernetes_reporting,
            object_capacity,
            object_alert_guidance,
            object_reporting,
            object_summary,
        )
    )
    for token in forbidden:
        assert token not in all_source


def test_operational_dashboard_standard_is_family_owned() -> None:
    standard = read('docs/design/patterns/OPERATIONAL_DASHBOARD.md')
    audit = read('docs/design/audits/OPERATIONAL_DASHBOARD_FAMILY_ALIGNMENT_AUDIT_2026_08_24.md')

    assert '# KAORI Operational Dashboard Pattern v1.4' in standard
    assert 'Kubernetes Operations Dashboard and Object Storage Operations Dashboard' in standard
    assert 'Dashboard family consistency' in standard
    assert 'future KAORI operational dashboards' in standard
    assert 'same four workspace tabs' in audit
    assert 'future operational dashboards' in audit
