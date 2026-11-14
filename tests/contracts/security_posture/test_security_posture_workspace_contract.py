"""Security Posture MVP contracts: navigation, RBAC, source boundary and reusable UI."""

import re
from datetime import UTC, datetime, timedelta
from html import unescape
from pathlib import Path

import yaml
from flask import Flask, render_template_string
from jinja2 import Environment

from app.common.pagination import build_pagination_window, pagination_payload
from app.common.workspace_navigation import build_sidebar_navigation
from app.security_posture.presentation import (
    _scanner_coverage_state,
    _security_severity_distribution,
    build_security_posture,
)

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


class FakeUser:
    is_authenticated = True

    def __init__(self, permissions: set[str]) -> None:
        self.permissions = permissions

    def has_permission(self, key: str) -> bool:
        return key in self.permissions


def _security_sidebar(permissions: set[str], endpoint: str = 'security_posture.overview') -> list[dict]:
    app = Flask(__name__)
    for route, name in (
        ('/', 'welcome.index'),
        ('/settings/general', 'settings.general'),
        ('/settings/account', 'settings.account'),
        ('/security/', 'security_posture.overview'),
        ('/security/findings', 'security_posture.findings'),
        ('/artifact-registry/', 'artifact_registry.overview'),
        ('/artifact-registry/inventory', 'artifact_registry.inventory'),
        ('/artifact-registry/security', 'artifact_registry.security'),
        ('/artifact-registry/security/overview', 'artifact_registry.security_overview'),
        ('/artifact-registry/runtime', 'artifact_registry.runtime_overview'),
        ('/artifact-registry/governance', 'artifact_registry.governance'),
        ('/artifact-registry/analytics', 'artifact_registry.analytics'),
    ):
        app.add_url_rule(route, endpoint=name, view_func=lambda: 'ok')
    with app.test_request_context('/security/'):
        sections = build_sidebar_navigation(endpoint, FakeUser(permissions))
    return [item for section in sections for item in section['items'] if item['key'] == 'security_posture']


def test_assurance_security_parent_is_two_levels_and_permission_filtered() -> None:
    assert not _security_sidebar(set())
    assert not _security_sidebar({'artifact_registry.view'})
    security = _security_sidebar({'security_posture.view'})
    assert len(security) == 1
    assert security[0]['label'] == 'Security'
    assert security[0]['active']
    assert [child['label'] for child in security[0]['children']] == ['Overview', 'Findings']
    assert security[0]['children'][0]['active']

    findings = _security_sidebar({'security_posture.view'}, 'security_posture.findings')
    assert findings[0]['children'][1]['active']


def test_security_posture_rbac_is_canonical_and_source_permissions_remain_distinct() -> None:
    catalog = yaml.safe_load(read('app/definitions/catalogs/access/rbac/access.yaml'))
    assert any(item['key'] == 'security_posture' for item in catalog['control_modules'])
    assert any(item['key'] == 'security_posture.view' for item in catalog['permissions'])
    for role in catalog['system_roles']:
        if 'artifact_registry.view' in role['permissions']:
            assert 'security_posture.view' in role['permissions']

    routes = read('app/security_posture/routes.py')
    assert routes.count("@permission_required('security_posture.view')") == 2
    assert routes.count("current_user.has_permission('artifact_registry.view')") == 2
    assert 'HarborClient' not in routes


def test_findings_is_bounded_read_only_and_requires_qualified_evidence() -> None:
    presentation = read('app/security_posture/presentation.py')
    assert 'SUCCESSFUL_REGISTRY_SCAN_STATUSES' in presentation
    assert 'RegistryProject.integration_instance_id.in_(source_ids)' in presentation
    assert 'func.count(func.distinct(RegistryWorkloadBinding.id))' in presentation
    assert "RegistryWorkloadBinding.match_type == 'digest'" in presentation
    assert "RegistryWorkloadBinding.match_type != 'digest'" in presentation
    assert "correlation['status'] == 'Ready'" in presentation
    assert 'paginate_query(' in presentation
    assert 're.fullmatch(' in presentation
    assert 'HarborClient' not in presentation
    assert 'if include_overview_summary and source_ids:' in presentation
    assert 'grouped.order_by(None).subquery()' in presentation
    assert "'severity_distribution': severity_distribution" in presentation
    assert 'requests.get(' not in presentation


def test_security_pages_use_approved_dashboard_and_registry_components() -> None:
    overview = read('app/templates/security_posture/overview.html')
    findings = read('app/templates/security_posture/findings.html')
    for html in (overview, findings):
        Environment().parse(html)
        assert 'components/page_hero.html' in html
    assert 'components/operational_dashboard_workspace.html' in overview
    assert 'page_hero.context_card(' in overview
    assert 'page_hero.blocked_context_body(' in overview
    assert "page_hero.intro('layout-dashboard', 'Security Posture', 'shield-alert')" in overview
    assert 'page_hero.shell_classes()' in overview
    assert 'page_hero.layout_classes()' in overview
    assert 'components/section_intro.html' in overview
    assert 'data-security-posture-insights' in overview
    assert 'lg:col-span-7' in overview
    assert 'lg:col-span-5' in overview
    assert 'components/progress_bar.html' in overview
    assert 'data-security-snapshot-grid' in overview
    assert 'data-security-runtime-impact' in overview
    assert 'data-security-evidence-confidence' in overview
    assert 'components/resource_posture_grid.html' in overview
    assert 'components/operational_metric_card.html' not in overview
    assert 'components/table.html' in overview
    assert 'data-security-posture-cve-registry' in overview
    assert 'components/table_registry.html' in overview
    assert 'registry.filter_form(' in overview
    assert 'registry.footer(' in overview
    assert 'table_ui.inventory_block_header(' in overview
    assert 'components/states/_empty_state.html' in overview
    assert 'components/states/_empty_state.html' in findings
    assert 'Security Evidence Prerequisites' in overview
    for tab in ('overview', 'capacity', 'signals', 'reporting'):
        assert f"dashboard_workspace.panel('{tab}'" in overview
    assert 'components/table_registry.html' in findings
    assert 'components/section_intro.html' in findings
    assert 'No CVE records' in findings
    assert 'This does not confirm' in findings
    assert "'security_posture.findings'" in findings
    assert '[5, 10, 25, 50]' in findings
    assert 'artifact_registry.security_cve_impact' in findings


def test_security_posture_is_registered_without_new_sidebar_renderer() -> None:
    catalog = read('app/common/workspace_navigation_catalog.py')
    bootstrap = read('app/bootstrap/blueprints.py')
    breadcrumbs = read('app/common/navigation.py')
    assert "key='security_posture'" in catalog
    assert "section='Assurance'" in catalog
    assert "label='Security'" in catalog
    assert 'security_posture_bp' in bootstrap
    assert "endpoint.startswith('security_posture.')" in breadcrumbs
    assert "BreadcrumbItem('Security', 'shield-alert')" in breadcrumbs
    assert 'data-kaori-sidebar-workspace' in read('app/templates/components/navigation/sidebar.html')


def test_security_permission_alone_never_queries_registry_evidence(monkeypatch) -> None:
    def forbidden() -> None:
        raise AssertionError('Registry provider should not be queried without artifact_registry.view')

    monkeypatch.setattr('app.security_posture.presentation._providers', forbidden)
    posture = build_security_posture(can_view_registry=False)
    assert posture['scan_status']['label'] == 'No Authorized Sources'
    assert posture['rows'] == []
    assert not posture['has_complete_security_evidence']
    assert posture['pagination']['per_page'] == 5
    assert posture['severity_distribution'] == []


def _render_workspace_page(name: str, posture: dict, **options: bool | str) -> str:
    """Compile imported KAORI macros and render the real page body without shell auth."""
    app = Flask(__name__, template_folder=str(ROOT / 'app/templates'))
    routes = (
        ('/security/', 'security_posture.overview'),
        ('/security/findings', 'security_posture.findings'),
        ('/integrations/registry', 'integrations.registry'),
        ('/artifact-registry/security', 'artifact_registry.security'),
        ('/artifact-registry/runtime', 'artifact_registry.runtime'),
        ('/intelligence/recommendations', 'intelligence.recommendations'),
        ('/reports/', 'reports.overview'),
        ('/artifact-registry/security/cve/<string:cve_id>/impact', 'artifact_registry.security_cve_impact'),
    )
    for path, endpoint in routes:
        app.add_url_rule(path, endpoint=endpoint, view_func=lambda **_kwargs: '')
    app.jinja_env.filters['user_datetime'] = lambda value: value.isoformat() if value else 'Not Collected'
    app.jinja_env.filters['environment_name'] = lambda value, empty='': value or empty

    template = read(f'app/templates/security_posture/{name}.html')
    template = template.replace('{% extends "layouts/app.html" %}', '', 1)
    template = re.sub(r'{% block title %}.*?{% endblock title %}', '', template, count=1, flags=re.S)
    template = template.replace('{% block dashboard_content %}', '', 1)
    template = template.replace('{% endblock dashboard_content %}', '', 1)
    with app.test_request_context('/security/' if name == 'overview' else '/security/findings'):
        return render_template_string(
            template,
            posture=posture,
            active_tab=options.get('active_tab', 'overview'),
            can_view_intelligence=options.get('can_view_intelligence', False),
            can_view_reports=options.get('can_view_reports', False),
            can_manage_integrations=options.get('can_manage_integrations', False),
        )


def _renderable_posture(authorized: bool = True) -> dict:
    page = pagination_payload(
        build_pagination_window(total_items=12 if authorized else 0, page=2 if authorized else 1, per_page=5)
    )
    return {
        'authorized_registry': authorized,
        'sources': 1 if authorized else 0,
        'scan_status': {'label': 'Observed', 'tone': 'normal'},
        'runtime_status': {'status': 'Ready', 'tone': 'normal'},
        'scanned_artifacts': 2,
        'artifacts_total': 2,
        'affected_artifacts': 1,
        'has_complete_security_evidence': authorized,
        'scan_updated_label': 'Updated 1m ago',
        'last_scan': datetime.now(UTC) if authorized else None,
        'severity_distribution': [
            {'label': 'Critical', 'count': 1, 'tone': 'critical'},
            {'label': 'High', 'count': 0, 'tone': 'warning'},
        ]
        if authorized
        else [],
        'runtime_binding_summary': {'digest': 1, 'reference': 0},
        'pagination': page,
        'search': 'CVE-2022-1586',
        'severity': 'critical',
        'severity_options': ('critical', 'high', 'medium', 'low', 'negligible'),
        'rows': [
            {
                'cve_id': 'CVE-2022-1586',
                'impact_available': authorized,
                'severity': 'Critical',
                'finding_count': 2,
                'artifact_count': 1,
                'binding_count': 1,
                'digest_binding_count': 1,
                'reference_binding_count': 0,
                'observed_at': None,
            }
        ]
        if authorized
        else [],
    }


def test_security_overview_reuses_governance_hero_and_dashboard_tabs() -> None:
    html = _render_workspace_page('overview', _renderable_posture())
    assert 'kaori-hero-shell' in html
    assert 'Assurance Boundary' in html
    assert 'Security Evidence' in html
    assert 'Provider Authority' in html
    assert 'Evidence Boundary' in html
    assert 'Review CVE Findings' in html
    assert 'data-kaori-dashboard-framework="operational-v1"' in html
    assert 'Security Exposure Signals' not in html
    assert 'Operational Signal Overview' not in html
    assert 'data-kaori-tab-variant="integrated-workspace"' in html
    assert 'Review Registry Security' not in html
    assert '/security/findings' in html
    assert 'data-kaori-hero-context-extension' not in html


def test_security_assurance_hero_omits_oversized_registry_cta_but_preserves_context() -> None:
    html = _render_workspace_page('overview', _renderable_posture(), can_manage_integrations=True)
    hero = html.split('kaori-hero-shell', 1)[1].split('</section>', 1)[0]
    assert 'Provider Authority' in hero
    assert 'Artifact Registry' in hero
    assert 'Evidence Boundary' in hero
    assert 'Committed' in hero
    assert 'Security Evidence' in hero
    assert 'Assurance Boundary' in hero
    assert 'Open Registry Integrations' not in hero
    assert '/integrations/registry' not in hero
    assert 'Operational Signal Scope' not in hero
    assert 'data-kaori-hero-context-extension' not in hero
    assert 'data-kaori-hero-status-strip' not in hero
    assert hero.count('data-kaori-hero-context-metric') == 2
    assert 'Review CVE Findings' in hero
    assert 'Overview' in hero

    shared_hero = read('app/templates/components/page_hero.html')
    assert '{% if action_label and action_href %}' in shared_hero
    assert 'context_single_action_classes()' in shared_hero
    assert 'context_extension' not in shared_hero
    assert "context_header('Dashboard Context', 'Operational Signal Scope', 'scan-search')" in shared_hero


def test_security_overview_blocks_do_not_touch_and_analysis_has_one_outer_card() -> None:
    html = _render_workspace_page('overview', _renderable_posture())
    assert 'data-security-overview-layout' in html
    assert 'data-security-overview-tabs' in html
    assert 'Exposure &amp; Runtime Evidence' in html
    assert html.count('data-security-posture-insights') == 1
    assert 'lg:border-t-0 lg:border-l' in html
    assert html.index('data-security-snapshot-grid') < html.index('data-security-posture-insights')
    assert html.index('data-security-posture-insights') < html.index('data-security-overview-tabs')


def test_security_snapshot_renders_unavailable_evidence_without_global_all_clear() -> None:
    posture = _renderable_posture()
    posture['scan_status'] = {'label': 'Partial / Stale', 'tone': 'warning'}
    posture['scan_updated_label'] = 'Updated 32d ago'
    posture['has_complete_security_evidence'] = False
    html = _render_workspace_page('overview', posture)
    assert 'Security Snapshot' in html
    assert 'Partial / Stale' in html
    assert 'Updated 32d ago' in html
    assert 'data-kaori-hero-context-extension' not in html
    assert 'Partial, stale or unavailable evidence cannot establish an all-clear.' in html


def test_security_snapshot_replaces_four_independent_kpi_cards() -> None:
    html = _render_workspace_page('overview', _renderable_posture())
    assert 'Security Snapshot' in html
    assert 'data-security-snapshot-grid' in html
    assert 'data-kaori-metric-density="compact"' not in html
    assert 'data-security-exposure-signals' not in html
    assert 'Security Exposure Signals' not in html
    assert 'Scan Coverage' in html
    assert 'Affected Artifact Digests' in html
    assert 'Runtime Correlation' in html
    assert 'Evidence Freshness' in html
    assert 'Provider Authority' in html
    assert 'Evidence Boundary' in html
    assert 'data-security-posture-insights' in html
    assert html.index('data-security-snapshot-grid') < html.index('data-security-posture-insights')

    snapshot = read('app/templates/security_posture/overview.html')
    assert 'posture_grid.render(snapshot_metrics, columns=4)' in snapshot
    assert 'columns=4' in snapshot
    assert 'metric_card.render(' not in snapshot
    assert 'components/resource_posture_grid.html' in snapshot
    # The canonical component remains available to other operational dashboards.
    metric = read('app/templates/components/operational_metric_card.html')
    assert 'compact=false' in metric
    assert "scope_label='Active Scope'" in metric


def test_security_analysis_is_one_shared_card_with_internal_peer_sections() -> None:
    template = read('app/templates/security_posture/overview.html')
    assert "section_card.render('Exposure & Runtime Evidence'" in template
    assert "section_card.render('Exposure by Severity'" not in template
    assert "section_card.render('Runtime & Evidence'" not in template
    assert 'lg:col-span-7' in template
    assert 'lg:col-span-5' in template
    assert 'lg:border-t-0 lg:border-l' in template
    assert 'data-security-runtime-impact' in template
    assert 'data-security-evidence-confidence' in template
    assert 'data-security-overview-layout' in template
    assert 'data-security-overview-tabs' in template
    assert 'class="space-y-5" data-security-overview-layout' in template
    assert 'progress_bar.semantic_bar(scan_coverage' in template
    assert template.index('data-security-snapshot-grid') < template.index('data-security-posture-insights')
    assert template.index('data-security-posture-insights') < template.index('security_tabs =')


def test_security_assurance_overview_uses_source_backed_exposure_hierarchy() -> None:
    html = _render_workspace_page('overview', _renderable_posture())
    assert 'data-security-snapshot-grid' in html
    assert 'Exposure &amp; Runtime Evidence' in html
    assert 'lg:col-span-7' in read('app/templates/security_posture/overview.html')
    assert 'lg:col-span-5' in read('app/templates/security_posture/overview.html')
    for label in ('Scan Coverage', 'Affected Artifact Digests', 'Runtime Correlation', 'Evidence Freshness'):
        assert label in html
    for label in ('Exposure by Severity', 'Runtime Impact', 'Evidence Confidence'):
        assert label in html
    assert '1 · 100%' in html
    assert '0 · 0%' in html
    assert 'data-security-severity-distribution' in html
    assert 'role="progressbar"' in html
    assert 'data-security-posture-cve-registry' in html
    assert 'CVE-2022-1586' in html
    assert '/artifact-registry/security/cve/CVE-2022-1586/impact' in html
    assert '0 mutable/other' in html
    assert 'No provider scan or mutation runs here.' in html
    assert 'data-security-investigation-handoff' in html
    assert 'sipgas-web' not in html  # mockup examples must never become product data
    assert 'Exposure Trend' not in html  # no committed historical series exists


def test_security_findings_registry_uses_full_table_and_embedded_handoff() -> None:
    html = _render_workspace_page('overview', _renderable_posture())
    template = read('app/templates/security_posture/overview.html')
    assert 'data-security-posture-cve-registry' in html
    assert 'data-security-posture-cve-table' in html
    assert 'data-security-investigation-handoff' in html
    assert html.count('data-security-investigation-handoff') == 1
    assert '2 scanner findings' in html
    assert 'View All Findings' in html
    assert 'Validate Runtime Impact' in html
    assert 'data-security-posture-cve-registry' in template
    assert "section_card.render('Investigation Handoff'" not in template
    assert 'table_ui.title_cell(row.cve_id' not in template
    assert 'flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1' in template
    assert template.index('data-security-posture-cve-table') < template.index('data-security-investigation-handoff')
    assert template.index('data-security-investigation-handoff') < template.index('registry.footer(')


def test_security_overview_cve_registry_is_filterable_htmx_and_url_paginated() -> None:
    html = _render_workspace_page('overview', _renderable_posture())
    template = read('app/templates/security_posture/overview.html')
    assert 'id="security-posture-cve-registry"' in html
    assert 'data-kaori-canonical-registry-filter="security-posture-cve-registry"' in html
    assert 'data-kaori-canonical-registry-footer="security-posture-cve-registry"' in html
    assert 'data-kaori-canonical-registry-pagination="security-posture-cve-registry"' in html
    assert 'data-kaori-page-size-control="security-posture-overview-cve"' in html
    assert 'hx-target="#security-posture-cve-registry"' in html
    assert 'hx-select="#security-posture-cve-registry"' in html
    assert 'hx-indicator="#security-posture-cve-loading"' in html
    assert 'name="tab" value="overview"' in html
    assert 'name="q"' in html
    assert 'name="severity"' in html
    assert 'name="per_page"' in html
    assert 'Reload Evidence' in html
    assert 'Clear Filters' in html
    assert 'data-kaori-clear-filters' in html
    assert 'tab=overview' in html
    assert 'page=1' in html
    assert 'page=3' in html
    assert 'data-kaori-info-tip-variant="guide"' in html
    assert 'components/table_registry.html' in template
    assert 'Loading CVE findings' in template
    assert '[5, 10, 25, 50]' in template
    for option in ('5', '10', '25', '50'):
        assert f'<option value="{option}"' in html


def test_security_overview_cve_registry_empty_filter_is_not_a_safety_verdict() -> None:
    posture = _renderable_posture()
    posture['rows'] = []
    posture['pagination'] = pagination_payload(build_pagination_window(total_items=0, page=1, per_page=5))
    posture['search'] = 'CVE-9999-999999'
    html = _render_workspace_page('overview', posture)
    assert 'No CVEs match this filter' in html
    assert 'No match does not prove safety.' in html
    assert 'data-kaori-canonical-registry-footer="security-posture-cve-registry"' in html
    assert 'Showing 0' in html
    assert 'Clear Filters' in html


def test_security_overview_filter_params_preserve_unfiltered_scope_totals() -> None:
    routes = read('app/security_posture/routes.py')
    overview_route = routes.split('def overview() -> ResponseReturnValue:', 1)[1]
    overview_route = overview_route.split('@security_posture_bp.get', 1)[0]
    assert "search=request.args.get('q', '', type=str)" in overview_route
    assert "severity=request.args.get('severity', '', type=str)" in overview_route
    assert "page=request.args.get('page', 1, type=int) or 1" in overview_route
    assert "per_page=request.args.get('per_page', 5, type=int) or 5" in overview_route
    assert 'include_overview_summary=True' in overview_route

    presentation = read('app/security_posture/presentation.py')
    assert 'scoped_cve_findings = scoped_findings.filter(all_cve_ids.like(' in presentation
    assert 'grouped = _grouped_security_cves(scoped_cve_findings)' in presentation
    assert 'filtered_grouped = _grouped_security_cves(filtered_findings)' in presentation
    assert 'severity_summary = grouped.order_by(None).subquery()' in presentation
    assert 'binding_totals = scoped_cve_findings.outerjoin(' in presentation
    assert 'paginate_query(' in presentation


def test_security_investigation_recommendations_are_permission_filtered() -> None:
    allowed = _render_workspace_page('overview', _renderable_posture(), can_view_intelligence=True)
    denied = _render_workspace_page('overview', _renderable_posture(), can_view_intelligence=False)
    assert 'Open Recommendations' in allowed
    assert 'Open Recommendations' not in denied
    assert 'Validate Runtime Impact' in denied


def test_security_hero_surfaces_stale_scanner_status_not_runtime_readiness() -> None:
    posture = _renderable_posture()
    posture['scan_status'] = {'label': 'Stale', 'tone': 'warning'}
    html = _render_workspace_page('overview', posture)
    hero = html.split('kaori-hero-shell', 1)[1].split('</section>', 1)[0]
    assert 'Stale' in hero
    assert 'Ready' not in hero
    assert '/security/findings' in hero


def test_security_exposure_section_uses_canonical_intro_and_source_guide() -> None:
    html = _render_workspace_page('overview', _renderable_posture())
    template = read('app/templates/security_posture/overview.html')
    assert 'Security Exposure Assessment' in html
    assert 'Review qualified CVE severity, runtime impact, and scanner confidence.' in html
    assert 'data-security-exposure-section' in html
    assert 'data-kaori-info-tip-variant="guide"' in html
    assert 'Open guide: Security Exposure Assessment Guide' in html
    assert 'Missing, changed, or stale evidence means exposure is unknown, never zero.' in html
    assert "section_intro.render('Security Exposure Assessment'" in template
    assert 'header_badge=exposure_guide' in template
    assert 'data-security-snapshot-grid' in html
    assert html.index('data-security-snapshot-grid') < html.index('data-security-exposure-section')
    assert html.index('data-security-exposure-section') < html.index('data-security-overview-tabs')


def test_security_context_and_unknown_runtime_messages_fit_one_line_on_desktop() -> None:
    template = read('app/templates/security_posture/overview.html')
    assert "('shield-check', 'Evidence Boundary', 'Committed', 'KAORI-normalized evidence')" in template
    assert 'Correlation not Ready; runtime exposure is unknown.' in template
    assert 'sm:whitespace-nowrap' in template
    assert 'Binding totals are unavailable until committed correlation is Ready.' not in template
    stale = _renderable_posture()
    stale['runtime_status'] = {'status': 'Inputs Changed', 'tone': 'warning'}
    html = _render_workspace_page('overview', stale)
    assert 'Correlation not Ready; runtime exposure is unknown.' in html
    assert 'KAORI-normalized evidence' in html
    runtime_panel = html.split('data-security-runtime-impact', 1)[1].split('data-security-evidence-confidence', 1)[0]
    assert 'Not Collected' not in runtime_panel


def test_security_assurance_runtime_impact_requires_ready_correlation() -> None:
    posture = _renderable_posture()
    posture['runtime_status'] = {'status': 'Stale', 'tone': 'warning'}
    posture['runtime_binding_summary'] = {'digest': 7, 'reference': 2}
    html = _render_workspace_page('overview', posture)
    assert 'Correlation not Ready; runtime exposure is unknown.' in html
    runtime_panel = html.split('data-security-runtime-impact', 1)[1].split('data-security-evidence-confidence', 1)[0]
    assert '>7<' not in runtime_panel
    assert '>2<' not in runtime_panel
    assert 'Strong identity' not in html


def test_security_assurance_labels_preserve_shared_tab_identity_and_bounds() -> None:
    html = unescape(_render_workspace_page('overview', _renderable_posture(), active_tab='capacity'))
    for label in ('Exposure Analysis', 'Assets & Impact', 'Findings & Investigation', 'Evidence & Sources'):
        assert label in html
    for key in ('overview', 'capacity', 'signals', 'reporting'):
        assert f'security-posture-overview-tab-{key}' in html
        assert f'security-posture-overview-panel-{key}' in html
    assert 'data-kaori-tab-variant="integrated-workspace"' in html
    shared = read('app/templates/components/operational_dashboard_workspace.html')
    assert 'navigation(prefix, aria_label, tabs=none)' in shared
    assert 'tabs if tabs is not none else standard_tabs' in shared
    assert "('overview', 'Operations Overview', 'activity')" in shared
    assert "('capacity', 'Capacity & Demand', 'gauge')" in shared


def test_security_distinct_cve_severity_projection_preserves_unknown_without_false_total() -> None:
    distribution = _security_severity_distribution({0: 2, 1: 1, 5: 3})
    assert distribution[0] == {'label': 'Critical', 'count': 2, 'tone': 'critical'}
    assert distribution[1] == {'label': 'High', 'count': 1, 'tone': 'warning'}
    assert distribution[2]['count'] == 0
    assert distribution[-1] == {'label': 'Unknown', 'count': 3, 'tone': 'unknown'}
    assert sum(row['count'] for row in distribution) == 6


def test_security_overview_table_renders_complete_server_paged_results() -> None:
    posture = _renderable_posture()
    posture['rows'] = [{**posture['rows'][0], 'cve_id': f'CVE-2022-{2000 + index}'} for index in range(7)]
    posture['pagination'] = pagination_payload(build_pagination_window(total_items=7, page=1, per_page=10))
    html = _render_workspace_page('overview', posture)
    assert 'CVE-2022-2000' in html
    assert 'CVE-2022-2004' in html
    assert 'CVE-2022-2005' in html
    assert 'CVE-2022-2006' in html
    assert 'Showing 1' in html
    assert '7 of 7' in html
    assert 'name="per_page"' in html
    assert re.search(r'<option value="10"\\s+selected', html)
    assert 'posture.rows[:5]' not in read('app/templates/security_posture/overview.html')


def test_security_assurance_stale_scanner_is_not_runtime_all_clear() -> None:
    posture = _renderable_posture()
    posture['scan_status'] = {'label': 'Stale', 'tone': 'warning'}
    posture['scan_updated_label'] = 'Updated 32d ago'
    posture['has_complete_security_evidence'] = False
    html = _render_workspace_page('overview', posture)
    assert 'Stale' in html
    assert 'Updated 32d ago' in html
    assert 'Partial, stale or unavailable evidence cannot establish an all-clear.' in html
    assert 'Kubernetes binding generation can be Ready while scanner evidence is Stale.' in html
    assert 'Ready' in html


def test_security_overview_blocks_without_eligible_source_without_inventing_kpis() -> None:
    posture = _renderable_posture(False)
    posture['scan_status'] = {'label': 'No Authorized Sources', 'tone': 'unknown'}
    posture['scanned_artifacts'] = 0
    posture['artifacts_total'] = 0
    posture['affected_artifacts'] = 0
    html = _render_workspace_page('overview', posture)
    assert 'data-kaori-blocked-state' in html
    assert 'Registry Evidence Required' in html
    assert 'No eligible committed Registry evidence' in html
    assert 'Security Evidence Prerequisites' in html
    assert 'data-kaori-dashboard-framework="operational-v1"' not in html


def test_security_findings_renders_shared_filters_and_exact_cve_drilldown() -> None:
    html = _render_workspace_page('findings', _renderable_posture())
    assert 'CVE-2022-1586' in html
    assert '1 digest' in html
    assert '0 mutable/other' in html
    assert 'not distinct applications' in html
    assert '/artifact-registry/security/cve/CVE-2022-1586/impact' in html
    assert 'data-kaori-canonical-registry-footer="security-posture-findings-registry"' in html
    assert 'name="severity"' in html
    assert 'name="per_page"' in html
    assert 'page=1' in html
    assert 'page=3' in html
    assert 'No CVE records' not in html


def test_security_findings_renders_no_source_as_unqualified_not_safe() -> None:
    html = _render_workspace_page('findings', _renderable_posture(False))
    assert 'No CVE records' in html
    assert 'This does not confirm' in html
    assert '/artifact-registry/security/cve/CVE-2022-1586/impact' not in html


def test_scanner_coverage_state_reports_missing_partial_stale_and_current() -> None:
    now = datetime.now(UTC)
    cases = [
        (0, 0, 0, None, 'Not Collected'),
        (1, 5, 0, None, 'Not Collected'),
        (1, 5, 3, now - timedelta(hours=1), 'Partial'),
        (1, 5, 3, now - timedelta(days=2), 'Partial / Stale'),
        (1, 5, 5, now - timedelta(days=2), 'Stale'),
        (1, 5, 5, now - timedelta(minutes=5), 'Observed'),
    ]
    for count, total, scanned, observation, expected in cases:
        state = _scanner_coverage_state(
            source_count=count,
            artifact_total=total,
            scanned_artifacts=scanned,
            oldest_scan=observation,
        )
        assert state['label'] == expected
        expected_tone = 'normal' if expected == 'Observed' else 'unknown' if expected == 'Not Collected' else 'warning'
        assert state['tone'] == expected_tone
