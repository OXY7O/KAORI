from pathlib import Path

import pytest
from flask import Flask, render_template_string
from jinja2 import Environment
from werkzeug.exceptions import NotFound

from app.artifact_registry.security.cve_impact import normalize_cve_id
from app.common.pagination import build_pagination_window, pagination_payload

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('cve-2026-12345', 'CVE-2026-12345'),
        ('  CVE-2025-1234  ', 'CVE-2025-1234'),
        ('CVE-2024-123456', 'CVE-2024-123456'),
    ],
)
def test_cve_impact_requires_canonical_exact_identity(value: str, expected: str) -> None:
    assert normalize_cve_id(value) == expected


@pytest.mark.parametrize(
    'value',
    [
        '',
        'PHP',
        'GHSA-1234-5678-9999',
        'CVE-2026-1234%25',
        'CVE-2026-1234/other',
        'CVE-2026-12',
        'CVE-2026-1234 extra',
        'CVE-2026-1234' + '9' * 70,
    ],
)
def test_cve_impact_rejects_malformed_or_broad_lookup(value: str) -> None:
    with pytest.raises(NotFound):
        normalize_cve_id(value)


def test_cve_impact_read_model_uses_last_good_scan_and_source_qualified_runtime() -> None:
    read_model = read('app/artifact_registry/security/cve_impact.py')
    assert 'SUCCESSFUL_REGISTRY_SCAN_STATUSES' in read_model
    assert 'group_by(RegistryScanSnapshot.artifact_id)' in read_model
    assert 'func.upper(RegistryVulnerability.vulnerability_id) == canonical_cve' in read_model
    assert 'RegistryProject.integration_instance_id.in_(source_ids)' in read_model
    assert 'RegistryWorkloadBinding.artifact_id.in_(' in read_model
    assert '_runtime_snapshot_state(correlation_prerequisites())' in read_model
    assert "correlation['status'] == 'Ready'" in read_model
    assert 'paginate_query(' in read_model
    assert 'HarborClient' not in read_model
    assert 'requests.get(' not in read_model


def test_cve_impact_view_is_permissioned_and_uses_existing_registry_navigation() -> None:
    routes = read('app/artifact_registry/routes.py')
    view = routes.split("@artifact_registry_bp.get('/security/cve/<string:cve_id>/impact')", 1)[1]
    view = view.split("@artifact_registry_bp.get('/security/supply-chain')", 1)[0]
    assert "@permission_required('artifact_registry.view')" in view
    assert 'build_cve_runtime_impact(' in view

    source = read('app/templates/artifact_registry/partials/_security_workspace.html')
    page = read('app/templates/artifact_registry/security_cve_impact.html')
    Environment().parse(source)
    Environment().parse(page)

    assert "url_for('artifact_registry.security_cve_impact'" in source
    assert 'components/page_hero.html' in page
    assert 'components/snapshot_context_bar.html' in page
    assert 'components/table_registry.html' in page
    assert "page_param='finding_page'" in page
    assert "page_param='runtime_page'" in page
    assert 'Impact completeness is not verified' in page
    assert 'This does not prove the application fleet is unaffected' in page
    assert "url_for('artifact_registry.runtime', artifact_id=row.artifact_id)" in page


def test_cve_impact_footer_renders_required_path_identity_for_rows_and_pages() -> None:
    """Regression: #2606, a required cve_id previously caused HTTP 500."""
    app = Flask(__name__, template_folder=str(ROOT / 'app/templates'))
    app.add_url_rule(
        '/artifact-registry/security/cve/<string:cve_id>/impact',
        endpoint='artifact_registry.security_cve_impact',
        view_func=lambda cve_id: cve_id,
    )
    page = pagination_payload(build_pagination_window(total_items=12, page=2, per_page=5))
    with app.test_request_context('/artifact-registry/security/cve/CVE-2022-1586/impact?finding_page=2&runtime_page=3'):
        rendered = render_template_string(
            """{% import "components/table_registry.html" as registry %}
{{ registry.footer('artifact_registry.security_cve_impact',
    'cve-findings', 'cve-loading', page,
    {'cve_id': 'CVE-2022-1586', 'runtime_page': 3},
    [5, 10, 25, 50], page_param='finding_page') }}""",
            page=page,
        )
    assert 'action="/artifact-registry/security/cve/CVE-2022-1586/impact"' in rendered
    assert 'hx-get="/artifact-registry/security/cve/CVE-2022-1586/impact"' in rendered
    assert 'name="runtime_page" value="3"' in rendered
    assert 'name="finding_page" value="1"' in rendered
    assert 'finding_page=1' in rendered
    assert 'finding_page=3' in rendered
    assert 'runtime_page=3' in rendered


def test_registry_footer_without_route_identity_retains_existing_action() -> None:
    app = Flask(__name__, template_folder=str(ROOT / 'app/templates'))
    app.add_url_rule(
        '/artifact-registry/security',
        endpoint='artifact_registry.security',
        view_func=lambda: '',
    )
    page = pagination_payload(build_pagination_window(total_items=0, page=1, per_page=5))
    with app.test_request_context('/artifact-registry/security'):
        rendered = render_template_string(
            """{% import "components/table_registry.html" as registry %}
{{ registry.footer('artifact_registry.security', 'registry', 'loading', page, {},
                   [5, 10, 25, 50]) }}""",
            page=page,
        )
    assert 'action="/artifact-registry/security"' in rendered
    assert 'hx-get="/artifact-registry/security"' in rendered


def test_cve_impact_runtime_footer_keeps_other_table_page() -> None:
    app = Flask(__name__, template_folder=str(ROOT / 'app/templates'))
    app.add_url_rule(
        '/artifact-registry/security/cve/<string:cve_id>/impact',
        endpoint='artifact_registry.security_cve_impact',
        view_func=lambda cve_id: cve_id,
    )
    page = pagination_payload(build_pagination_window(total_items=12, page=3, per_page=5))
    with app.test_request_context('/artifact-registry/security/cve/CVE-2022-1586/impact?finding_page=2&runtime_page=3'):
        rendered = render_template_string(
            """{% import "components/table_registry.html" as registry %}
{{ registry.footer('artifact_registry.security_cve_impact',
    'cve-runtime', 'cve-runtime-loading', page,
    {'cve_id': 'CVE-2022-1586', 'finding_page': 2},
    [5, 10, 25, 50], page_param='runtime_page') }}""",
            page=page,
        )
    assert 'action="/artifact-registry/security/cve/CVE-2022-1586/impact"' in rendered
    assert 'hx-get="/artifact-registry/security/cve/CVE-2022-1586/impact"' in rendered
    assert 'name="finding_page" value="2"' in rendered
    assert 'name="runtime_page" value="1"' in rendered
    assert 'finding_page=2' in rendered
    assert 'runtime_page=2' in rendered
