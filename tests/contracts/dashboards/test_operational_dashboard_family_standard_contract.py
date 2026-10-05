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
    framework = read('app/templates/components/operational_dashboard_workspace.html')

    for source in (kubernetes, object_storage):
        assert 'components/operational_dashboard_workspace.html' in source
        assert 'dashboard_workspace.controller(' in source
        assert 'dashboard_workspace.navigation(' in source
        assert 'hx-trigger="revealed"' in source

    assert kubernetes.count('dashboard_workspace.panel(') == 4
    assert '{% for tab_key, tab_label, tab_icon in dashboard_workspace.standard_tabs %}' in object_storage
    assert object_storage.count('dashboard_workspace.panel(') == 1

    for token in (
        "('overview', 'Operations Overview', 'activity')",
        "('capacity', 'Capacity & Demand', 'gauge')",
        "('signals', 'Signals & Actions', 'bell-ring')",
        "('reporting', 'Reporting', 'file-text')",
        'moveTab(currentTab, direction, prefix)',
        "url.searchParams.set('tab', tab)",
        "window.history.replaceState({}, '', url)",
    ):
        assert token in framework

    assert 'kubernetes/dashboard/partials/_hero.html' in kubernetes
    assert 'kubernetes/dashboard/partials/_signal_overview.html' in kubernetes
    assert 'storage/object_storage/dashboard/partials/_hero.html' in object_storage
    assert 'storage/object_storage/dashboard/partials/_signal_overview.html' in object_storage
    assert 'class="mt-5 space-y-5"' in kubernetes
    assert 'class="mt-5 space-y-5"' in object_storage


def test_kubernetes_dashboard_blocked_onboarding_uses_shared_integration_contract() -> None:
    content = read('app/templates/kubernetes/dashboard/partials/_content.html')
    onboarding = read('app/templates/components/cluster/_onboarding_banner.html')

    assert '{% include "components/cluster/_onboarding_banner.html" %}' in content
    for local_override in (
        'cluster_onboarding_steps =',
        'cluster_onboarding_action_url =',
        'cluster_onboarding_action_label =',
        'cluster_onboarding_action_icon =',
    ):
        assert local_override not in content

    assert 'blocked_state_steps = ["Open Cluster Integrations", "Register Cluster", "Run Sync"]' in onboarding
    assert "blocked_state_action_url = url_for('integrations.kubernetes')" in onboarding
    assert 'blocked_state_action_label = "Open Cluster Integrations"' in onboarding
    assert 'blocked_state_action_icon = "plug-zap"' in onboarding
    assert "url_for('cluster.add_cluster')" not in onboarding
    assert 'blocked_state_action_label = "Add Cluster"' not in onboarding


def test_operational_dashboards_share_peer_grid_and_reporting_proportions() -> None:
    kubernetes = combined(KUBERNETES)
    object_storage = combined(OBJECT_STORAGE)
    reporting_workspace = read('app/templates/components/reporting_dashboard_workspace.html')

    for source in (kubernetes, object_storage):
        assert source.count('peer_content_grid.layout_classes()') >= 4
        assert "column_classes('primary', 'seven-five')" in source
        assert "column_classes('secondary', 'seven-five')" in source

    alert_response_workspace = read('app/templates/components/operational_alert_response.html')
    assert 'Controlled Response Flow' in alert_response_workspace
    assert 'Governed Reporting Flow' in reporting_workspace
    assert '<span class="font-semibold text-content-primary">One-time</span> · Manual' in reporting_workspace
    assert 'Generate manually' not in reporting_workspace


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


def test_kubernetes_cluster_health_uses_canonical_pagination_payload() -> None:
    service = read('app/kubernetes/dashboard/service.py')
    cluster_health = read('app/kubernetes/dashboard/sections/cluster_health.py')
    schema = read('app/kubernetes/dashboard/schema.py')
    template = read('app/templates/kubernetes/dashboard/partials/_cluster_health.html')

    assert 'from app.common.pagination import paginate_sequence' in service
    assert 'def paginate_sequence(' not in cluster_health
    assert 'ClusterHealthPagination' not in cluster_health
    assert 'class ClusterHealthPagination' not in schema
    assert 'pagination_payload(build_pagination_window(total_items=0))' in schema
    assert 'for size in pagination.allowed_per_page' in template


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
    object_service = read('app/storage/object_storage/dashboard/service.py')
    object_alert_guidance = read(
        'app/templates/storage/object_storage/dashboard/partials/_alert_response_guidance.html'
    )
    object_reporting = read('app/templates/storage/object_storage/dashboard/partials/_reporting_guidance.html')
    object_summary = read('app/templates/storage/object_storage/dashboard/partials/_reporting_summary.html')

    assert 'Committed analytics available' in freshness
    assert 'Generated reports are retained artifacts, separate from current Kubernetes health.' in freshness
    assert 'No immediate scaling required.' in capacity
    assert 'Validate requests/limits, growth, and planned deployments against current worker headroom.' in capacity
    assert (
        'Verify the selected cluster Metrics Source and kube-state-metrics node-role labels, then reload the snapshot.'
        in capacity
    )
    assert 'Worker-node CPU, memory, and pod headroom; control-plane nodes excluded.' in kubernetes_capacity
    assert 'Apply the approved capacity/workload change' in kubernetes_capacity
    assert 'KAORI Alert Intelligence case evidence is temporarily unavailable.' in kubernetes_alerts
    reporting_workspace = read('app/templates/components/reporting_dashboard_workspace.html')
    assert 'components/reporting_dashboard_workspace.html' in kubernetes_reporting
    assert 'components/reporting_dashboard_workspace.html' in object_reporting
    assert "'Committed cluster evidence'" in kubernetes_reporting
    assert "'Committed Object Storage evidence'" in object_reporting
    assert 'Governed Reporting Flow' in reporting_workspace
    assert 'Review before reuse.' in reporting_workspace
    assert 'Committed capacity, usage, headroom, and response path.' in object_capacity
    assert "'Worker Data Needed'" in object_service
    assert "'Worker Data Required'" not in object_service
    assert (
        'Capacity uses the committed Object Storage Analytics snapshot; no live provider query is issued.'
        in object_capacity
    )
    assert (
        'Developing capacity, request-path, or availability risk. Investigate before escalation.'
        in object_alert_guidance
    )
    assert 'Low-risk operational signal. Validate relevance, recurrence, and scope.' in object_alert_guidance
    assert 'components/reporting_dashboard_workspace.html' in object_summary

    kubernetes_response = read('app/templates/kubernetes/dashboard/partials/_alert_response_guidance.html')
    kubernetes_summary = read('app/templates/kubernetes/dashboard/partials/_reporting_summary.html')
    assert 'Run the approved response for the confirmed scope within safety guardrails.' in kubernetes_response
    assert (
        'Run the approved storage response for the confirmed scope within safety guardrails.' in object_alert_guidance
    )
    assert 'components/reporting_dashboard_workspace.html' in kubernetes_summary
    assert 'components/reporting_dashboard_workspace.html' in object_summary

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
        'Execute only the approved runbook or governed change for the confirmed scope while preserving permission and safety guardrails.',
        'Execute only the approved runbook or governed storage change for the confirmed scope while preserving safety guardrails.',
        'Configured recurring plans that define when reports are generated automatically.',
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


def test_response_and_reporting_flows_use_current_shared_governance_owners() -> None:
    kubernetes_response = read('app/templates/kubernetes/dashboard/partials/_alert_response_guidance.html')
    object_response = read('app/templates/storage/object_storage/dashboard/partials/_alert_response_guidance.html')
    kubernetes_reporting = read('app/templates/kubernetes/dashboard/partials/_reporting_guidance.html')
    object_reporting = read('app/templates/storage/object_storage/dashboard/partials/_reporting_guidance.html')
    tenant = read('app/templates/kubernetes/tenant/partials/_tenant_setup_workspace.html')

    assert 'Tenant Governance Flow' in tenant
    assert 'components/numbered_governance_steps.html' in tenant

    shared_response = read('app/templates/components/operational_alert_response.html')
    assert 'components/numbered_governance_steps.html' in shared_response
    assert 'Controlled Response Flow' in shared_response

    for source in (kubernetes_response, object_response):
        assert 'components/operational_alert_response.html' in source
        assert 'components/operational_flow_steps.html' not in source
        assert 'alert_response_steps' in source
        assert 'before acting on the signal' in source
        assert 'establish an accountable owner' in source
        assert 'remains auditable' in source
        for step in ('Validate', 'Triage', 'Investigate', 'Respond', 'Verify', 'Record'):
            assert f"'{step}'" in source

    reporting_workspace = read('app/templates/components/reporting_dashboard_workspace.html')
    for source in (kubernetes_reporting, object_reporting):
        assert 'components/reporting_dashboard_workspace.html' in source
        assert 'reporting_workspace.guidance(' in source
        assert 'components/operational_flow_steps.html' not in source

    assert 'reporting_steps' in reporting_workspace
    assert 'Governed Reporting Flow' in reporting_workspace
    for step in ('Validate', 'Select', 'Create', 'Generate', 'Schedule', 'Retain'):
        assert f"'{step}'" in reporting_workspace


def test_alerts_summary_is_bounded_to_five_in_both_reference_dashboards() -> None:
    kubernetes_summary = read('app/templates/kubernetes/dashboard/partials/_alerts_summary.html')
    kubernetes_builder = read('app/kubernetes/dashboard/sections/alerts.py')
    kubernetes_service = read('app/kubernetes/dashboard/service.py')
    object_summary = read('app/templates/storage/object_storage/dashboard/partials/_alerts_summary.html')
    object_service = read('app/storage/object_storage/dashboard/service.py')

    shared_alert_summary = read('app/templates/components/operational_alert_summary.html')
    assert 'rows[:5]' in shared_alert_summary
    assert 'rows=dashboard.alerts_snapshot.items' in kubernetes_summary
    assert 'for item in raw_items[:5]' in kubernetes_builder
    assert 'for case in cases[:5]' in kubernetes_service
    assert 'rows=dashboard.alerts.rows' in object_summary
    assert "for case in posture['cases'][:5]" in object_service

    for source in (shared_alert_summary, kubernetes_builder, kubernetes_service, object_service):
        assert '[:6]' not in source
        assert '[:3]' not in source


def test_recent_report_activity_is_bounded_to_four_in_both_reference_dashboards() -> None:
    kubernetes_summary = read('app/templates/kubernetes/dashboard/partials/_reporting_summary.html')
    kubernetes_builder = read('app/kubernetes/dashboard/sections/reporting.py')
    object_summary = read('app/templates/storage/object_storage/dashboard/partials/_reporting_summary.html')
    object_service = read('app/storage/object_storage/dashboard/service.py')
    reporting_workspace = read('app/templates/components/reporting_dashboard_workspace.html')

    assert 'components/reporting_dashboard_workspace.html' in kubernetes_summary
    assert 'components/reporting_dashboard_workspace.html' in object_summary
    assert 'reporting.latest_reports[:4]' in reporting_workspace
    assert 'query_all(Report, selected_cluster_id, limit=4)' in kubernetes_builder
    assert 'recent = reports_query.order_by(Report.created_at.desc()).limit(4).all()' in object_service

    for source in (reporting_workspace, kubernetes_builder, object_service):
        assert 'limit=5' not in source
        assert 'latest_reports[:5]' not in source


def test_operational_dashboard_inner_presentation_is_shared_across_three_consumers() -> None:
    signal = read('app/templates/components/operational_signal_overview.html')
    evidence = read('app/templates/components/operational_evidence_tile.html')
    alerts = read('app/templates/components/operational_alert_summary.html')
    response = read('app/templates/components/operational_alert_response.html')
    recommendations = read('app/templates/components/operational_recommendation_cards.html')

    for wrapper in (
        read('app/templates/kubernetes/dashboard/partials/_signal_overview.html'),
        read('app/templates/storage/object_storage/dashboard/partials/_signal_overview.html'),
        read('app/templates/artifact_registry/partials/_overview_signal_overview.html'),
    ):
        assert 'components/operational_signal_overview.html' in wrapper
        assert 'signal_overview.render(' in wrapper

    assert 'Operational Signal Overview' in signal
    assert '{% set signal_content = caller() %}' in signal
    assert '{{ signal_content|safe }}' in signal
    assert signal.count('caller()') == 1
    assert signal.index('{% set signal_content = caller() %}') < signal.index('{% call operational_section_card.render(')
    assert 'macro snapshot(' in evidence
    assert 'macro freshness(' in evidence
    assert 'rows[:5]' in alerts
    assert 'components/numbered_governance_steps.html' in response
    assert "'Recommended Actions'" in recommendations

    kubernetes_capacity = read('app/templates/kubernetes/dashboard/partials/_capacity_snapshot.html')
    object_hero = read('app/templates/storage/object_storage/dashboard/partials/_hero.html')
    assert "operational_callout.render('Capacity Action Flow'" not in kubernetes_capacity
    assert "'Open Object Storage Integrations'" in object_hero


def test_operational_dashboard_standard_is_family_owned() -> None:
    standard = read('docs/design/patterns/OPERATIONAL_DASHBOARD.md')
    audit = read('docs/design/audits/OPERATIONAL_DASHBOARD_FAMILY_FAST_TRACK_ALIGNMENT_AUDIT_2026_09_29.md')

    assert '# KAORI Operational Dashboard Pattern v1.7' in standard
    assert 'Kubernetes Operations Dashboard and Object Storage Operations Dashboard' in standard
    assert 'Dashboard family consistency' in standard
    assert 'Registry/Harbor and Source Control/GitHub' in standard
    assert 'components/operational_dashboard_workspace.html' in standard
    assert 'components/reporting_dashboard_workspace.html' in standard
    assert 'same four workspace tabs' in audit
    assert 'Registry/Harbor and Source Control/GitHub' in audit
    assert 'Tenant Governance Flow' in audit
    assert 'Issue #758' in audit
    assert 'five-record Alerts Summary preview boundary' in audit
    assert 'four-record Recent Report Activity preview boundary' in audit
