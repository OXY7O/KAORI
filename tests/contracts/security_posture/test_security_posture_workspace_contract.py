"""Security Posture MVP contracts: navigation, RBAC, source boundary and reusable UI."""

from pathlib import Path

import yaml
from flask import Flask
from jinja2 import Environment

from app.common.workspace_navigation import build_sidebar_navigation
from app.security_posture.presentation import build_security_posture

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
    return [
        item
        for section in sections
        for item in section['items']
        if item['key'] == 'security_posture'
    ]


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
    assert "SUCCESSFUL_REGISTRY_SCAN_STATUSES" in presentation
    assert 'RegistryProject.integration_instance_id.in_(source_ids)' in presentation
    assert 'func.count(func.distinct(RegistryWorkloadBinding.id))' in presentation
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
