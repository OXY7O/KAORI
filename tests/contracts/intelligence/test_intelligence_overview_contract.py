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

    for text in ('Active Alerts', 'critical alerts', 'verify'):
        assert text in template or text in overview


def test_intelligence_overview_uses_clean_summary_information_architecture() -> None:
    template = read('app/templates/intelligence/overview.html')

    for section in (
        'Intelligence Posture',
        'Intelligence Workspaces',
        'Operational Boundary',
    ):
        assert section in template

    for removed_section in (
        'Operational Intelligence Snapshot',
        'Operator Attention',
        'Coverage & Readiness',
        'Trust & Ownership Boundaries',
        'Overview Stops at Summary',
        'Current Priorities',
    ):
        assert removed_section not in template

    assert 'payload.priorities' not in template
    assert '_recommendation_records.html' not in template
    assert '_alert_ops_active_table.html' not in template
    assert 'Affected Assets' not in template
    assert 'Evidence Details' not in template


def test_intelligence_overview_has_four_direct_kpi_cards() -> None:
    overview = read('app/intelligence/overview.py')
    template = read('app/templates/intelligence/overview.html')

    assert "'kpi_cards': _kpi_cards(" in overview
    assert 'payload.kpi_cards' in template

    for label in ('Active Findings', 'Active Alerts', 'Rule Coverage', 'Pending Governance'):
        assert f"'label': '{label}'" in overview

    for action in (
        'View Recommendations',
        'View Alert Intelligence',
        'View Rule Catalog',
        'View Automation Control',
    ):
        assert action in overview


def test_intelligence_overview_posture_is_compact_and_cross_workspace() -> None:
    overview = read('app/intelligence/overview.py')
    template = read('app/templates/intelligence/overview.html')

    assert "'posture_items': _posture_items(" in overview
    assert 'payload.posture_items' in template

    for label in ('Critical Attention', 'Evidence Freshness', 'Automation Readiness'):
        assert f"'label': '{label}'" in overview

    assert 'Overview is database-backed; provider collection and refresh stay worker-owned.' in overview


def test_intelligence_overview_exposes_four_owned_workspaces_as_simple_rows() -> None:
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

    assert 'workspace.primary_value' in template
    assert 'workspace.secondary_value' in template
    assert 'Open Workspace' in template


def test_intelligence_overview_keeps_one_explicit_operational_boundary() -> None:
    template = read('app/templates/intelligence/overview.html')

    assert 'Operational Boundary' in template
    assert 'Overview only presents aggregate Intelligence posture.' in template
    assert 'Provider collection and refresh remain worker-owned; this page reads committed KAORI state only.' in template
    assert 'Evidence Boundary' not in template
    assert 'Alert Lifecycle' not in template
    assert 'Automation Boundary' not in template


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
