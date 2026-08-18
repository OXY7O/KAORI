from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT / 'app' / 'templates' / 'kubernetes' / 'dashboard'
CONTENT = DASHBOARD_DIR / 'partials' / '_content.html'
HERO = DASHBOARD_DIR / 'partials' / '_hero.html'
BLOCKED_HERO = ROOT / 'app' / 'templates' / 'components' / 'cluster' / '_hero_blocked_context.html'
SIGNAL_OVERVIEW = DASHBOARD_DIR / 'partials' / '_signal_overview.html'
REPORTING_GUIDANCE = DASHBOARD_DIR / 'partials' / '_reporting_guidance.html'
WORKSPACE_TABS = ROOT / 'app' / 'templates' / 'components' / 'workspace_tabs.html'
METRIC_CARD = ROOT / 'app' / 'templates' / 'components' / 'operational_metric_card.html'
KPI_CARDS = DASHBOARD_DIR / 'partials' / '_kpi_cards.html'
TOP_CONSUMERS = DASHBOARD_DIR / 'partials' / '_top_consumers.html'
ROUTES = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'routes.py'
SERVICE = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'service.py'
README = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'README.md'
STANDARD = ROOT / 'docs' / 'design' / 'patterns' / 'OPERATIONAL_DASHBOARD.md'
AUDIT = ROOT / 'docs' / 'design' / 'audits' / 'KUBERNETES_OPERATIONS_DASHBOARD_ALIGNMENT_AUDIT_2026_08.md'
QUALITY_GATE = ROOT / 'scripts' / 'quality_gate.sh'
FEATURE_COVERAGE = ROOT / 'scripts' / 'verify_feature_test_coverage.py'
CHARACTERIZATION = ROOT / 'tests' / 'kubernetes' / 'dashboard' / 'test_kubernetes_dashboard_characterization.py'
SNAPSHOT_FLOW_TEST = ROOT / 'tests' / 'kubernetes' / 'dashboard' / 'test_kubernetes_dashboard_snapshot_flow.py'
TOP_CONSUMERS_SOURCE = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'sections' / 'top_consumers.py'
SCHEMA = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'schema.py'
KPI_BUILDER = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'sections' / 'kpis.py'
UTILS = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'utils.py'
FRESHNESS = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'sections' / 'freshness.py'
SECTIONS_INIT = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'sections' / '__init__.py'
UNIT_TEST = ROOT / 'tests' / 'unit' / 'kubernetes' / 'dashboard' / 'test_kubernetes_dashboard_domain.py'
SECURITY_TEST = ROOT / 'tests' / 'security' / 'kubernetes' / 'dashboard' / 'test_kubernetes_dashboard_security.py'
RENDERING_TEST = ROOT / 'tests' / 'rendering' / 'kubernetes' / 'dashboard' / 'test_kubernetes_dashboard_rendering.py'
INTEGRATION_TEST = (
    ROOT / 'tests' / 'integration' / 'kubernetes' / 'dashboard' / 'test_kubernetes_dashboard_repository.py'
)
E2E_TEST = ROOT / 'tests' / 'e2e' / 'kubernetes' / 'dashboard' / 'test_kubernetes_dashboard_smoke.py'

SECTION_PARTIALS = (
    '_signal_overview.html',
    '_cluster_health.html',
    '_inventory_summary.html',
    '_data_freshness.html',
    '_capacity_snapshot.html',
    '_forecast_risk.html',
    '_top_consumers.html',
    '_alerts_summary.html',
    '_recommended_actions.html',
    '_reporting_summary.html',
    '_alert_response_guidance.html',
    '_reporting_guidance.html',
    '_section_loading.html',
)

STALE_COPY = (
    'Live Signals Enabled',
    'Select a Cluster for Live Signals',
    'AlertManager',
    'PDF output',
    'stored PDF',
)


def _read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f'Missing operational dashboard contract file: {path.relative_to(ROOT)}')
    return path.read_text(encoding='utf-8')


def _require(source: str, tokens: tuple[str, ...], owner: str) -> None:
    missing = [token for token in tokens if token not in source]
    if missing:
        raise AssertionError(f'{owner}: missing canonical tokens: {", ".join(missing)}')


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in getattr(tree, 'body', []):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f'dashboard route boundary: missing function {name}')


def _has_permission_decorator(function: ast.FunctionDef, permission: str) -> bool:
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call) or not decorator.args:
            continue
        called = decorator.func
        if isinstance(called, ast.Name) and called.id == 'permission_required':
            value = decorator.args[0]
            return isinstance(value, ast.Constant) and value.value == permission
    return False


def _call_lines(function: ast.FunctionDef, name: str) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        called = node.func
        if isinstance(called, ast.Name) and called.id == name:
            lines.append(node.lineno)
    return sorted(lines)


def _verify_route_authorization_order(routes: str) -> None:
    tree = ast.parse(routes, filename=str(ROUTES))
    index = _function(tree, 'index')
    section = _function(tree, 'section')
    if not _has_permission_decorator(index, 'dashboard.view'):
        raise AssertionError('dashboard route boundary: index must require dashboard.view')
    if not _has_permission_decorator(section, 'dashboard.view'):
        raise AssertionError('dashboard route boundary: section must require dashboard.view')

    for node in getattr(tree, 'body', []):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            called = decorator.func if isinstance(decorator, ast.Call) else decorator
            if isinstance(called, ast.Attribute) and called.attr == 'before_request':
                raise AssertionError(
                    'dashboard route boundary: authorization-sensitive clusterless responses must not be owned by before_request'
                )

    cluster_lines = _call_lines(section, 'has_registered_clusters')
    data_lines = _call_lines(section, 'get_dashboard_section')
    if len(cluster_lines) != 1 or len(data_lines) != 1 or cluster_lines[0] >= data_lines[0]:
        raise AssertionError(
            'dashboard route boundary: protected section must resolve cluster readiness before dashboard data access'
        )


def verify() -> None:
    content = _read(CONTENT)
    hero = _read(HERO)
    blocked_hero = _read(BLOCKED_HERO)
    signal_overview = _read(SIGNAL_OVERVIEW)
    reporting_guidance = _read(REPORTING_GUIDANCE)
    workspace_tabs = _read(WORKSPACE_TABS)
    metric_card = _read(METRIC_CARD)
    kpi_cards = _read(KPI_CARDS)
    top_consumers = _read(TOP_CONSUMERS)
    routes = _read(ROUTES)
    service = _read(SERVICE)
    readme = _read(README)
    standard = _read(STANDARD)
    audit = _read(AUDIT)
    quality_gate = _read(QUALITY_GATE)
    feature_coverage = _read(FEATURE_COVERAGE)
    characterization = _read(CHARACTERIZATION)
    snapshot_flow_test = _read(SNAPSHOT_FLOW_TEST)
    top_consumers_source = _read(TOP_CONSUMERS_SOURCE)
    schema = _read(SCHEMA)
    kpi_builder = _read(KPI_BUILDER)
    utils = _read(UTILS)
    freshness = _read(FRESHNESS)
    sections_init = _read(SECTIONS_INIT)
    unit_test = _read(UNIT_TEST)
    security_test = _read(SECURITY_TEST)
    rendering_test = _read(RENDERING_TEST)
    integration_test = _read(INTEGRATION_TEST)
    e2e_test = _read(E2E_TEST)

    _require(
        hero,
        (
            'cluster_blocked_scope = "Dashboard Readiness"',
            'cluster_blocked_state_label = "Dashboard State"',
            'components/cluster/_hero_blocked_context.html',
            "page_hero.context_header('Dashboard Context', 'Operational Signal Scope', 'scan-search')",
        ),
        'dashboard hero readiness',
    )
    _require(
        blocked_hero,
        (
            "'Connected Clusters', '0', 'No Kubernetes connection available'",
            "blocked_state_label, 'Blocked', 'Cluster access is required'",
        ),
        'shared Kubernetes blocked hero',
    )

    blocked_branch = hero.split('{% if cluster_onboarding.is_blocked %}', 1)[1].split('{% else %}', 1)[0]
    if 'page_hero.context_panel_classes()' in blocked_branch:
        raise AssertionError(
            'dashboard hero readiness: blocked branch must not wrap the shared blocker in a second context panel'
        )

    _require(
        content,
        (
            'import "components/workspace_tabs.html" as workspace_tabs',
            'import "components/peer_content_grid.html" as peer_content_grid',
            "('overview', 'Operations Overview', 'activity')",
            "('capacity', 'Capacity & Demand', 'gauge')",
            "('signals', 'Signals & Actions', 'bell-ring')",
            "('reporting', 'Reporting', 'file-text')",
            'workspace_tabs.render(',
            'moveTab(currentTab, direction, prefix)',
            "url.searchParams.set('tab', tab)",
            "window.history.replaceState({}, '', url)",
            'id="kubernetes-dashboard-panel-overview"',
            'id="kubernetes-dashboard-panel-capacity"',
            'id="kubernetes-dashboard-panel-signals"',
            'id="kubernetes-dashboard-panel-reporting"',
            'peer_content_grid.layout_classes()',
            'hx-trigger="revealed"',
        ),
        'dashboard composition',
    )

    if content.count('peer_content_grid.layout_classes()') != 4:
        raise AssertionError('dashboard composition: expected four canonical peer-content grids')

    _require(
        workspace_tabs,
        (
            'data-kaori-tab-variant="integrated-workspace"',
            'role="tablist"',
            'role="tab"',
            ':aria-selected=',
            ':tabindex=',
            '@keydown.arrow-right.prevent',
            '@keydown.arrow-left.prevent',
            '@keydown.home.prevent',
            '@keydown.end.prevent',
        ),
        'integrated workspace tabs',
    )

    _require(
        signal_overview,
        (
            'Cluster Signals Available',
            'Select a Cluster for Detailed Signals',
            'hx-include="#dashboard-active-tab"',
            'hx-push-url="true"',
        ),
        'dashboard scope and signal wording',
    )

    _require(
        reporting_guidance,
        ('approved output', 'stored artifact', 'Controlled Reporting Flow', 'Reporting Tip'),
        'format-neutral reporting guidance',
    )

    for stale in STALE_COPY:
        dashboard_source = '\n'.join(path.read_text(encoding='utf-8') for path in sorted(DASHBOARD_DIR.rglob('*.html')))
        if stale in dashboard_source:
            raise AssertionError(f'dashboard templates still contain stale wording: {stale}')

    _require(
        metric_card,
        (
            "macro render(label, value, description, icon, source_label='Operational', scope_label='Active Scope')",
            'components/table_label.html',
            'bg-surface-card',
            'border-outline-default',
        ),
        'operational metric card',
    )
    if 'scope_tone' in metric_card or "tone='violet'" in metric_card:
        raise AssertionError('operational metric card still exposes unused presentation arguments')
    if 'semantic_tones' in kpi_cards or 'scope_tone' in kpi_cards:
        raise AssertionError('dashboard KPI template still contains dead tone mapping')

    _require(
        top_consumers,
        (
            'Select a cluster to view committed CPU and memory consumer signals.',
            'Committed memory consumer data is not available yet.',
            "'bg-kaori-primary' if item.signal_state == 'normal'",
        ),
        'dashboard top-consumer snapshot presentation',
    )
    if (
        'from Prometheus' in top_consumers
        or "'bg-status-info',\n                dashboard.top_consumers_snapshot.memory" in top_consumers
    ):
        raise AssertionError(
            'dashboard top-consumer presentation must use committed-snapshot wording and KAORI Violet normal-state ranking'
        )

    for name in SECTION_PARTIALS:
        source = _read(DASHBOARD_DIR / 'partials' / name)
        _require(
            source,
            ('components/operational_section_card.html', 'operational_section_card.render('),
            f'dashboard section {name}',
        )

    _verify_route_authorization_order(routes)

    _require(
        routes,
        (
            "@permission_required('dashboard.view')",
            "DASHBOARD_TABS = {'overview', 'capacity', 'signals', 'reporting'}",
            'CLUSTER_HEALTH_PAGE_SIZES = {5, 10, 25, 50}',
            'SECTION_TEMPLATES = {',
            'if has_registered_clusters() is False:',
        ),
        'dashboard route boundary',
    )

    _require(
        service,
        (
            'database-only dashboard shell',
            'committed worker snapshots only',
            'read_dashboard_snapshot(',
            'query_for_clusters(',
            'paginate_sequence(',
        ),
        'dashboard service boundary',
    )
    forbidden_live_imports = (
        'kubernetes.client',
        'prometheus_api_client',
        'requests.get',
        'httpx.get',
        'boto3.client',
    )
    for token in forbidden_live_imports:
        if token in service or token in routes:
            raise AssertionError(f'dashboard web boundary contains live provider access: {token}')

    if '**_: Any' in service:
        raise AssertionError('dashboard service still exposes a compatibility catch-all argument')
    if 'live_cluster' in service or 'live_cluster' in schema or 'get_live_cluster' in utils:
        raise AssertionError('dashboard internals still use misleading live-cluster naming for selected DB scope')
    kpi_schema = schema.split('class DashboardKpi:', 1)[1].split('@dataclass', 1)[0]
    if 'tone:' in kpi_schema or 'trend:' in kpi_schema or 'tone=' in kpi_builder:
        raise AssertionError('dashboard KPI model/builder still carries retired unused presentation fields')
    if 'build_hero_integration_meta' in freshness or 'build_hero_integration_meta' in sections_init:
        raise AssertionError('dashboard still contains the orphan Hero integration metadata builder')
    if 'def format_gib' in utils:
        raise AssertionError('dashboard still contains the unused duplicate format_gib helper')
    if 'returned by Prometheus' in top_consumers_source or 'Prometheus returned' in top_consumers_source:
        raise AssertionError('dashboard presentation still implies request-time Prometheus access')

    _require(
        readme,
        (
            'read-only operational projection over committed KAORI data',
            'OPERATIONAL_DASHBOARD.md` v1.3',
            'Arrow Left/Right, Home, and End keyboard navigation',
            'artifact-format neutral',
            'Web requests must not query Kubernetes, Metrics Source, or Alertmanager directly',
        ),
        'dashboard technical README',
    )

    _require(
        standard,
        (
            '# KAORI Operational Dashboard Pattern v1.3',
            'Context Icon Box',
            'Maintainability and performance contract',
            'Layered release evidence',
            '**Status:** Locked reference pattern',
            'Kubernetes Operations Dashboard',
            'Identity → Scope → Indicators → Peer analysis → Interpretation → Action',
            'Web requests read committed database rows and worker snapshots only',
            'Arrow Left/Right wrap through tabs',
            'Select a Cluster for Detailed Signals',
            'Reporting guidance must remain format-neutral',
            'Authorization must complete before clusterless onboarding',
            'tests/kubernetes/dashboard/test_kubernetes_dashboard_characterization.py',
            'scripts/verify_operational_dashboard_standard.py',
        ),
        'operational dashboard standard',
    )

    _require(
        audit,
        (
            'Approved as the canonical KAORI operational dashboard reference',
            'No visual redesign is required',
            'Corrections made without visual redesign',
            'Final Recheck v2',
            'Final Recheck v3',
            'authorization ordering',
            'behavioral characterization',
        ),
        'dashboard alignment audit',
    )

    if 'python scripts/verify_operational_dashboard_standard.py' not in quality_gate:
        raise AssertionError('scripts/quality_gate.sh does not execute the dashboard standard verifier')
    if 'tests/kubernetes/dashboard' not in quality_gate:
        raise AssertionError('scripts/quality_gate.sh does not explicitly execute Dashboard functional tests')
    if "'tests/kubernetes/dashboard/test_kubernetes_dashboard_characterization.py': 7" not in feature_coverage:
        raise AssertionError('Dashboard behavioral characterization is not protected by the feature coverage gate')

    layered_requirements = (
        "'tests/unit/kubernetes/dashboard/test_kubernetes_dashboard_domain.py': 3",
        "'tests/security/kubernetes/dashboard/test_kubernetes_dashboard_security.py': 3",
        "'tests/rendering/kubernetes/dashboard/test_kubernetes_dashboard_rendering.py': 2",
        "'tests/integration/kubernetes/dashboard/test_kubernetes_dashboard_repository.py': 1",
        "'tests/e2e/kubernetes/dashboard/test_kubernetes_dashboard_smoke.py': 2",
    )
    for requirement in layered_requirements:
        if requirement not in feature_coverage:
            raise AssertionError(f'Dashboard layered release evidence is not protected: {requirement}')

    _require(
        unit_test,
        ('test_dashboard_pagination_is_bounded', 'committed_snapshot_not_live_provider_query'),
        'dashboard unit evidence',
    )
    _require(
        security_test,
        ('authorization_boundary', 'no_direct_provider_client', 'no_blueprint_before_request'),
        'dashboard security evidence',
    )
    _require(
        rendering_test,
        ('valid_jinja', 'canonical_hero_tabs_table_status_and_pagination'),
        'dashboard rendering evidence',
    )
    _require(
        integration_test,
        ('sqlite+pysqlite:///:memory:', 'query_all', 'count_records', 'latest_record_timestamp'),
        'dashboard integration evidence',
    )
    _require(
        e2e_test,
        ('/dashboards/kubernetes/', 'Quick Actions', 'Notifications', 'kaoriNavbar'),
        'dashboard E2E evidence',
    )

    _require(
        characterization,
        (
            'test_lazy_section_authorization_runs_before_clusterless_blocker',
            'test_authorized_clusterless_section_renders_onboarding_without_data_read',
            'test_unknown_section_returns_404_before_cluster_probe',
            'test_authorized_section_reads_dashboard_only_after_cluster_readiness',
            'test_dashboard_tab_selection_is_bounded_to_canonical_tabs',
            'test_cluster_health_page_size_rejects_unbounded_values',
            'test_dashboard_index_requires_permission_before_building_context',
        ),
        'dashboard behavioral characterization',
    )
    if "return [cluster], [option], 'cluster-1', cluster" not in snapshot_flow_test:
        raise AssertionError('Dashboard snapshot-flow tests still use the retired five-value scope contract')
    if (
        'lambda _models, _selected' in snapshot_flow_test
        or 'models, clusters, options, None, None' in snapshot_flow_test
    ):
        raise AssertionError('Dashboard snapshot-flow tests still target retired service helper signatures')

    print(
        'KAORI operational dashboard standard passed: canonical composition, snapshot-only web boundary, '
        'authorization-first lazy sections, URL-backed keyboard-accessible tabs, shared style ownership, '
        'format-neutral reporting guidance, top-consumer snapshot semantics, behavioral release evidence, '
        'documentation, audit, and quality-gate enforcement match v1.3.'
    )


if __name__ == '__main__':
    verify()
