from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_intelligence_root_renders_dedicated_overview() -> None:
    routes = read('app/intelligence/routes.py')

    assert "@intelligence_bp.route('/')" in routes
    assert "@permission_required('intelligence.view')" in routes
    assert 'get_intelligence_overview_payload()' in routes
    assert "render_template('intelligence/overview.html', payload=payload)" in routes
    assert "redirect(url_for('intelligence.recommendations'))" not in routes
    assert Path('app/templates/intelligence/overview.html').exists()


def test_intelligence_overview_is_committed_database_state_only() -> None:
    overview = read('app/intelligence/overview.py')

    assert 'get_active_recommendation_findings()' in overview
    assert 'INTELLIGENCE_CATALOG' in overview
    assert 'Cluster.query.count()' in overview
    assert 'ObjectStorageSystem.query.count()' in overview
    assert 'db.session.query(' in overview
    assert 'AlertCase.workflow_state' in overview
    assert 'AlertSilence.query.filter' in overview
    assert 'NotificationDelivery.query.filter' in overview
    assert 'IntelligenceDecisionCandidate.query' in overview
    assert 'IntelligenceDecision.query' in overview
    assert 'KnowledgeRunbookRevision.query' in overview

    for forbidden in (
        'load_alerts_by_source',
        'load_alert_stream',
        'MetricsConsumer',
        'MinioClient',
        '.query_range(',
        '.custom_query(',
        'requests.get(',
        'requests.post(',
    ):
        assert forbidden not in overview


def test_intelligence_overview_surfaces_alert_operations_posture() -> None:
    overview = read('app/intelligence/overview.py')
    template = read('app/templates/intelligence/overview.html')

    assert "'alerts': alerts" in overview
    assert "'active': active" in overview
    assert "'verification_pending': verification_pending" in overview
    assert "'silenced': int(active_silences)" in overview
    assert "'resolved_24h': closed_24h" in overview
    assert "'delivery_failures': int(delivery_failures)" in overview
    assert "'postmortem_required': postmortem_required" in overview

    for text in (
        'Active Alert Cases',
        'Delivery Failures',
        'Resolved in 24h',
        'postmortem pending',
    ):
        assert text in template or text in overview


def test_intelligence_overview_uses_summary_first_information_architecture() -> None:
    template = read('app/templates/intelligence/overview.html')

    for section in (
        'Operational Intelligence Snapshot',
        'Operator Attention',
        'Coverage & Readiness',
        'Intelligence Workspaces',
        'Trust & Ownership Boundaries',
        'Overview Stops at Summary',
    ):
        assert section in template

    assert 'Current Priorities' not in template
    assert 'payload.priorities' not in template
    assert '_recommendation_records.html' not in template
    assert '_alert_ops_active_table.html' not in template
    assert 'Affected Assets' not in template
    assert 'Evidence Details' not in template


def test_intelligence_overview_exposes_four_owned_workspaces_as_navigation_rows() -> None:
    overview = read('app/intelligence/overview.py')
    template = read('app/templates/intelligence/overview.html')

    assert "'workspaces': _workspace_rows(" in overview
    assert 'payload.workspaces' in template

    for title in ('Recommendations', 'Alert Intelligence', 'Rule Catalog', 'Automation Control'):
        assert f"'title': '{title}'" in overview

    for endpoint in (
        'intelligence.recommendations',
        'alert_intelligence.index',
        'intelligence.catalog',
        'automation_control.index',
    ):
        assert endpoint in overview

    assert 'grid gap-4 px-4 py-4' in template
    assert 'workspace.action_label' in template


def test_intelligence_overview_uses_cross_workspace_attention_and_coverage_metrics() -> None:
    overview = read('app/intelligence/overview.py')
    template = read('app/templates/intelligence/overview.html')

    assert "'attention_metrics': _attention_metrics(" in overview
    assert "'coverage_metrics': _coverage_metrics(" in overview
    assert 'payload.attention_metrics' in template
    assert 'payload.coverage_metrics' in template

    for metric in (
        'Critical Recommendations',
        'Active Alert Cases',
        'Delivery Failures',
        'Pending Governance',
        'Managed Assets',
        'Rule Coverage',
        'Resolved in 24h',
        'Published Runbooks',
    ):
        assert metric in overview


def test_intelligence_overview_keeps_current_ownership_boundaries_explicit() -> None:
    template = read('app/templates/intelligence/overview.html')

    assert 'Evidence Boundary' in template
    assert 'Alert Lifecycle' in template
    assert 'Automation Boundary' in template
    assert 'The Overview never calls Prometheus, Thanos, Alertmanager, or Object Storage providers directly.' in template
    assert 'KAORI owns acknowledgement, assignment, notification policy, delivery silence, resolution evidence, postmortem, history, and archive lifecycle.' in template
    assert 'Stale or failed alert snapshots may remain visible to operators but cannot materialize new automation candidates.' in template


def test_intelligence_sidebar_and_welcome_enter_through_overview() -> None:
    sidebar = read('app/templates/components/navigation/intelligence_menu.html')
    welcome = read('app/welcome/shortcuts.py')
    navigation = read('app/common/navigation.py')

    overview_link = "('intelligence.index', 'layout-dashboard', 'Overview')"
    recommendations_link = "('intelligence.recommendations', 'sparkles', 'Recommendations')"
    assert overview_link in sidebar
    assert sidebar.index(overview_link) < sidebar.index(recommendations_link)
    assert "('intelligence.view', 'intelligence.index')" in welcome
    assert "'intelligence.index': 'Overview'" in navigation
    assert "endpoint.startswith(('intelligence.', 'alert_intelligence.', 'automation_control.'))" in navigation
