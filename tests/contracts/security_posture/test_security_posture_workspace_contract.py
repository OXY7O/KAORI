"""Security Posture MVP contracts: navigation, RBAC, source boundary and reusable UI."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from flask import Flask, render_template_string
from jinja2 import Environment

from app.common.pagination import build_pagination_window, pagination_payload
from app.common.workspace_navigation import build_sidebar_navigation
from app.security_posture.presentation import _scanner_coverage_state, build_security_posture

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
    assert 'requests.get(' not in presentation


def test_security_pages_use_approved_dashboard_and_registry_components() -> None:
    overview = read('app/templates/security_posture/overview.html')
    findings = read('app/templates/security_posture/findings.html')
    for html in (overview, findings):
        Environment().parse(html)
        assert 'components/page_hero.html' in html
    assert 'components/operational_dashboard_workspace.html' in overview
    assert 'page_hero.operational_dashboard(' in overview
    assert 'components/operational_signal_overview.html' in overview
    assert 'components/operational_metric_card.html' in overview
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


def test_security_overview_renders_operational_profile_and_signal_cards() -> None:
    html = _render_workspace_page('overview', _renderable_posture())
    assert 'data-kaori-hero-profile="operational-dashboard"' in html
    assert 'data-kaori-dashboard-framework="operational-v1"' in html
    assert 'Operational Signal Overview' in html
    assert 'data-kaori-tab-variant="integrated-workspace"' in html
    assert 'Review Registry Security' in html
    assert '/security/findings' in html


def test_security_overview_blocks_without_eligible_source_without_inventing_kpis() -> None:
    posture = _renderable_posture(False)
    posture['scan_status'] = {'label': 'No Authorized Sources', 'tone': 'unknown'}
    posture['scanned_artifacts'] = 0
    posture['artifacts_total'] = 0
    posture['affected_artifacts'] = 0
    html = _render_workspace_page('overview', posture)
    assert 'data-kaori-hero-state="blocked"' in html
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
