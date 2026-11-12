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


def test_cve_impact_uses_shared_balanced_hero_and_short_snapshot_scope() -> None:
    from app.common.navigation import build_navigation_breadcrumb

    page = read('app/templates/artifact_registry/security_cve_impact.html')
    Environment().parse(page)
    hero = page.split('page_hero.shell_classes()', 1)[1].split('snapshot_context_bar.render(', 1)[0]

    assert 'page_hero.layout_classes()' in hero
    assert 'page_hero.content_classes()' in hero
    assert "page_hero.context_card('Committed CVE correlation'" in hero
    assert 'impact.correlation.status' in hero
    assert 'impact.correlation.tone' in hero
    assert "'Affected Digests', impact.affected_artifacts" in hero
    assert "'Runtime Bindings', impact.binding_count" in hero
    assert "'Back to Vulnerabilities'" in hero
    assert "url_for('artifact_registry.security', q=impact.cve_id)" in hero
    assert "action_icon='arrow-left'" in hero
    assert 'table_ui.action_classes()' not in hero

    assert "scope_label='Registry × Kubernetes'" in page
    assert "scope_supporting='Committed evidence'" in page
    assert "coverage_supporting='Latest usable scans'" in page
    assert "' source' if impact.source_count == 1 else ' sources'" in page
    assert "' digest' if impact.affected_artifacts == 1 else ' digests'" in page
    assert "'Not Qualified' if not impact.evidence_ready else 'Current'" in page
    assert page.count('class="{{ table_ui.block_classes() }}"') == 2
    assert page.count("table_ui.table_classes('min-w-[60rem]')") == 2
    assert "page_param='finding_page'" in page
    assert "page_param='runtime_page'" in page
    assert 'Impact completeness is not verified' in page
    assert 'Workload names are not canonical application or Team identities.' in page

    assert build_navigation_breadcrumb('artifact_registry.security_cve_impact')[-1]['label'] == 'CVE Impact'
    assert build_navigation_breadcrumb('artifact_registry.security_overview')[-1]['label'] == 'Security Overview'
    assert build_navigation_breadcrumb('artifact_registry.security_supply_chain')[-1]['label'] == 'Supply Chain'


def test_cve_impact_evidence_tables_use_canonical_registry_patterns() -> None:
    """Exact CVE can match multiple findings and independent runtime bindings."""
    page = read('app/templates/artifact_registry/security_cve_impact.html')
    read_model = read('app/artifact_registry/security/cve_impact.py')
    shared_table = read('app/templates/components/table.html')
    Environment().parse(page)

    assert page.count('class="{{ table_ui.block_classes() }}"') == 2
    assert page.count('table_ui.inventory_block_header(') == 2
    assert page.count('class="overflow-x-auto"') == 2
    assert page.count("table_ui.table_classes('min-w-[60rem]')") == 2
    assert page.count('class="{{ table_ui.head_classes() }}"') == 2
    assert page.count('class="{{ table_ui.body_classes() }}"') == 2
    assert page.count('class="{{ table_ui.row_classes() }}"') == 2
    assert page.count('components/states/_empty_state.html') == 2
    assert page.count('aria-label="View runtime usage for ') == 2
    assert "title_extra=findings_badge" in page
    assert "title_extra=runtime_badge" in page
    assert "impact.finding_count ~ (' Finding'" in page
    assert "impact.binding_count ~ (' Binding'" in page
    assert 'table_label.metadata_label(' in page
    assert 'macro inventory_block_header(' in shared_table

    # Both lists are one-to-many even though the screenshot shows one row.
    assert 'for row in impact.finding_rows' in page
    assert 'for row in impact.runtime_rows' in page
    assert 'finding_items, finding_pagination = paginate_query(' in read_model
    assert 'binding_items, runtime_pagination = paginate_query(' in read_model
    assert "page_param='finding_page'" in page
    assert "page_param='runtime_page'" in page
    assert "impact.runtime_pagination.page" in page
    assert "impact.finding_pagination.page" in page
    assert page.count('[5, 10, 25, 50]') == 2

    # Identity, timestamps, qualified match confidence and source actions survive.
    for field in (
        'row.repository',
        'row.project',
        'row.source',
        'row.digest',
        'row.package',
        'row.installed_version',
        'row.fixed_version',
        'row.severity',
        'row.freshness.label',
        'row.observed_at|user_datetime',
        'row.cluster',
        'row.namespace',
        'row.workload',
        'row.pod',
        'row.container',
        'row.match.label',
        'row.match.description',
        'row.artifact_id',
    ):
        assert field in page

    assert 'Digest matches are stronger than mutable tag references.' in page
    assert 'Workload names are not canonical application or Team identities.' in page
    assert 'Correlation is not current; absence is unverified.' in page
    assert 'This does not prove the application fleet is unaffected' in page
    assert "url_for('artifact_registry.runtime', artifact_id=row.artifact_id)" in page
    assert page.count('colspan="5"') == 2
    assert 'data-kaori-empty-state' in read(
        'app/templates/components/states/_empty_state.html'
    )


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
