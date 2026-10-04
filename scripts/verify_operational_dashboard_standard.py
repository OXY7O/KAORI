from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT / 'app' / 'templates' / 'kubernetes' / 'dashboard'
CONTENT = DASHBOARD_DIR / 'partials' / '_content.html'
HERO = DASHBOARD_DIR / 'partials' / '_hero.html'
ONBOARDING_BANNER = ROOT / 'app' / 'templates' / 'components' / 'cluster' / '_onboarding_banner.html'
SIGNAL_OVERVIEW = DASHBOARD_DIR / 'partials' / '_signal_overview.html'
ALERT_SUMMARY = DASHBOARD_DIR / 'partials' / '_alerts_summary.html'
ALERT_GUIDANCE = DASHBOARD_DIR / 'partials' / '_alert_response_guidance.html'
REPORTING_GUIDANCE = DASHBOARD_DIR / 'partials' / '_reporting_guidance.html'
REPORTING_SUMMARY = DASHBOARD_DIR / 'partials' / '_reporting_summary.html'
ALERTS_BUILDER = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'sections' / 'alerts.py'
REPORTING_BUILDER = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'sections' / 'reporting.py'
OBJECT_DASHBOARD_DIR = ROOT / 'app' / 'templates' / 'storage' / 'object_storage' / 'dashboard'
OBJECT_CONTENT = OBJECT_DASHBOARD_DIR / 'partials' / '_content.html'
OBJECT_HERO = OBJECT_DASHBOARD_DIR / 'partials' / '_hero.html'
OBJECT_SIGNAL_OVERVIEW = OBJECT_DASHBOARD_DIR / 'partials' / '_signal_overview.html'
OBJECT_ALERT_SUMMARY = OBJECT_DASHBOARD_DIR / 'partials' / '_alerts_summary.html'
OBJECT_ALERT_GUIDANCE = OBJECT_DASHBOARD_DIR / 'partials' / '_alert_response_guidance.html'
OBJECT_REPORTING_GUIDANCE = OBJECT_DASHBOARD_DIR / 'partials' / '_reporting_guidance.html'
OBJECT_REPORTING_SUMMARY = OBJECT_DASHBOARD_DIR / 'partials' / '_reporting_summary.html'
OBJECT_DASHBOARD_SERVICE = ROOT / 'app' / 'storage' / 'object_storage' / 'dashboard' / 'service.py'
ARTIFACT_OVERVIEW = ROOT / 'app' / 'templates' / 'artifact_registry' / 'overview.html'
ARTIFACT_CONTENT = ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_content.html'
ARTIFACT_HERO = ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_hero.html'
ARTIFACT_SIGNAL_OVERVIEW = (
    ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_signal_overview.html'
)
ARTIFACT_REPORTING = ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_reporting.html'
ARTIFACT_CAPACITY = ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_capacity.html'
ARTIFACT_SIGNALS = ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_signals.html'
ARTIFACT_OPERATIONS = ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_operations.html'
ARTIFACT_PROVIDER_HEALTH = (
    ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_provider_health.html'
)
ARTIFACT_ROUTES = ROOT / 'app' / 'artifact_registry' / 'routes.py'
ARTIFACT_PRESENTATION = ROOT / 'app' / 'artifact_registry' / 'presentation.py'
PAGE_HERO = ROOT / 'app' / 'templates' / 'components' / 'page_hero.html'
WORKSPACE_TABS = ROOT / 'app' / 'templates' / 'components' / 'workspace_tabs.html'
DASHBOARD_WORKSPACE = ROOT / 'app' / 'templates' / 'components' / 'operational_dashboard_workspace.html'
REPORTING_WORKSPACE = ROOT / 'app' / 'templates' / 'components' / 'reporting_dashboard_workspace.html'
METRIC_CARD = ROOT / 'app' / 'templates' / 'components' / 'operational_metric_card.html'
TENANT_SETUP_WORKSPACE = (
    ROOT / 'app' / 'templates' / 'kubernetes' / 'tenant' / 'partials' / '_tenant_setup_workspace.html'
)
KPI_CARDS = DASHBOARD_DIR / 'partials' / '_kpi_cards.html'
TOP_CONSUMERS = DASHBOARD_DIR / 'partials' / '_top_consumers.html'
ROUTES = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'routes.py'
SERVICE = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'service.py'
README = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'README.md'
STANDARD = ROOT / 'docs' / 'design' / 'patterns' / 'OPERATIONAL_DASHBOARD.md'
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
    '_alert_response_guidance.html',
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


def _verify_dashboard_hero_profile(hero: str, object_hero: str, page_hero: str) -> None:
    _require(
        page_hero,
        (
            'macro operational_dashboard(',
            'data-kaori-hero-profile="operational-dashboard"',
            "context_metric('scan-search', 'Active Scope'",
            "context_metric('database-zap', 'Data Authority'",
            'metadata[:3]',
        ),
        'shared Operational Dashboard Hero profile',
    )
    _require(
        hero,
        (
            'page_hero.operational_dashboard(',
            "dashboard_state = 'blocked' if cluster_onboarding.is_blocked else 'normal'",
            "'Committed Snapshots'",
            'Kubernetes Operations',
            "'Dashboard'",
            "'Open Cluster Integrations'",
            "url_for('integrations.kubernetes')",
        ),
        'Kubernetes dashboard Hero profile consumer',
    )
    _require(
        object_hero,
        (
            'page_hero.operational_dashboard(',
            "'Committed Snapshots'",
            'Object Storage Operations',
            "'Dashboard'",
        ),
        'Object Storage dashboard Hero profile consumer',
    )
    for owner, source in (
        ('Kubernetes dashboard', hero),
        ('Object Storage dashboard', object_hero),
    ):
        for primitive in (
            'page_hero.shell_classes()',
            'page_hero.layout_classes()',
            'page_hero.content_classes()',
            'page_hero.context_panel_classes()',
        ):
            if primitive in source:
                raise AssertionError(f'{owner}: Hero profile consumer must not assemble {primitive} locally')


def _verify_artifact_registry_dashboard(
    overview: str,
    content: str,
    hero: str,
    signal_overview: str,
    reporting: str,
    capacity: str,
    signals: str,
    operations: str,
    provider_health: str,
    routes: str,
    presentation: str,
) -> None:
    _require(
        overview,
        (
            'artifact_registry/partials/_overview_content.html',
            'artifact-registry-dashboard-content',
        ),
        'Artifact Registry dashboard page shell',
    )
    _require(
        hero,
        (
            'page_hero.operational_dashboard(',
            'Artifact Registry Operations',
            "'Overview'",
            "'Committed Snapshots'",
            "'Open Registry Integrations'",
            "url_for('integrations.registry')",
        ),
        'Artifact Registry operational dashboard Hero consumer',
    )
    for primitive in (
        'page_hero.shell_classes()',
        'page_hero.layout_classes()',
        'page_hero.content_classes()',
        'page_hero.context_panel_classes()',
    ):
        if primitive in hero:
            raise AssertionError(
                f'Artifact Registry dashboard: Hero profile consumer must not assemble {primitive} locally'
            )

    _require(
        content,
        (
            'components/operational_dashboard_workspace.html',
            'dashboard_workspace.controller(',
            'dashboard_workspace.navigation(',
            'dashboard_workspace.panel(',
            'artifact_registry/partials/_overview_signal_overview.html',
            'artifact_registry/components/_setup_blocker.html',
        ),
        'Artifact Registry dashboard family composition',
    )
    _require(
        content,
        (
            'for tab_key, tab_label, tab_icon in dashboard_workspace.standard_tabs',
            "url_for('artifact_registry.overview_section', section=tab_key)",
            'hx-trigger="revealed"',
            'Preparing committed Artifact Registry dashboard evidence.',
        ),
        'Artifact Registry lazy canonical dashboard panels',
    )

    _require(
        signal_overview,
        (
            'Operational Signal Overview',
            'components/operational_metric_card.html',
            'provider_id',
            'hx-push-url="true"',
            'hx-include="#artifact-registry-dashboard-active-tab"',
            'All Registry Providers',
        ),
        'Artifact Registry scope and signal overview',
    )
    _require(
        operations,
        (
            'artifact_registry/partials/_overview_provider_health.html',
            'Inventory Snapshot',
            'Data Freshness',
            "current_user.has_permission('artifact_registry.sync')",
            "url_for('artifact_registry.sync_inventory')",
        ),
        'Artifact Registry Operations Overview parity',
    )
    _require(
        provider_health,
        (
            'Registry Provider Health Summary',
            'Security Signals',
            'Snapshot Sources',
            'components/pagination.html',
            "loading_bar_id='artifact-registry-provider-health-loading'",
            'hx-indicator="#artifact-registry-provider-health-loading"',
            'Inventory',
            'Metrics Source',
            'Security Evidence',
        ),
        'Artifact Registry provider health register',
    )
    _require(
        capacity,
        (
            'components/peer_content_grid.html',
            'artifact_registry/partials/_overview_capacity_snapshot.html',
            'artifact_registry/partials/_overview_forecast_risk.html',
            'artifact_registry/partials/_overview_top_consumers.html',
        ),
        'Artifact Registry capacity peer dashboard grammar',
    )
    _require(
        signals,
        (
            'components/peer_content_grid.html',
            'artifact_registry/partials/_overview_alerts_summary.html',
            'artifact_registry/partials/_overview_alert_response_guidance.html',
            'artifact_registry/partials/_overview_recommended_actions.html',
        ),
        'Artifact Registry signals peer dashboard grammar',
    )
    _require(
        reporting,
        (
            'components/reporting_dashboard_workspace.html',
            'reporting_workspace.summary(',
            'reporting_workspace.guidance(',
        ),
        'Artifact Registry reporting dashboard handoff',
    )
    if reporting.index('reporting_workspace.summary(') >= reporting.index('reporting_workspace.guidance('):
        raise AssertionError('Artifact Registry reporting must present summary before governed guidance')
    _require(
        routes,
        (
            "@permission_required('artifact_registry.view')",
            "request.args.get('provider_id', type=int)",
            "request.args.get('tab', 'overview', type=str)",
            "'overview': 'artifact_registry/partials/_overview_operations.html'",
            "'capacity': 'artifact_registry/partials/_overview_capacity.html'",
            "'signals': 'artifact_registry/partials/_overview_signals.html'",
            "'reporting': 'artifact_registry/partials/_overview_reporting.html'",
            'artifact_registry/partials/_overview_content.html',
        ),
        'Artifact Registry dashboard route boundary',
    )
    _require(
        presentation,
        (
            "allowed_tabs = {'overview', 'capacity', 'signals', 'reporting'}",
            'RegistryProject.integration_instance_id == selected_provider.id',
            "registry_metrics_readiness(provider).get('status') == 'ready'",
            "'scope_label': scope_label",
            "'capacity': capacity",
            "'alerts': alerts",
            "'recommended_actions': recommended_actions",
            "'reporting': reporting",
            "'label': 'Inventory Snapshot'",
            "'label': 'Metrics Snapshot'",
            "'label': 'Security Snapshot'",
            "'label': 'Analytics Snapshot'",
            "'kpis': [",
        ),
        'Artifact Registry committed dashboard projection',
    )
    for token in (
        'HarborClient(',
        'requests.get',
        'httpx.get',
    ):
        if token in routes or token in presentation:
            raise AssertionError(
                f'Artifact Registry dashboard web boundary contains live provider access: {token}'
            )


def verify() -> None:
    content = _read(CONTENT)
    hero = _read(HERO)
    onboarding_banner = _read(ONBOARDING_BANNER)
    signal_overview = _read(SIGNAL_OVERVIEW)
    alert_summary = _read(ALERT_SUMMARY)
    alert_guidance = _read(ALERT_GUIDANCE)
    reporting_guidance = _read(REPORTING_GUIDANCE)
    reporting_summary = _read(REPORTING_SUMMARY)
    alerts_builder = _read(ALERTS_BUILDER)
    reporting_builder = _read(REPORTING_BUILDER)
    object_content = _read(OBJECT_CONTENT)
    object_hero = _read(OBJECT_HERO)
    object_signal_overview = _read(OBJECT_SIGNAL_OVERVIEW)
    object_alert_summary = _read(OBJECT_ALERT_SUMMARY)
    object_alert_guidance = _read(OBJECT_ALERT_GUIDANCE)
    object_reporting_guidance = _read(OBJECT_REPORTING_GUIDANCE)
    object_reporting_summary = _read(OBJECT_REPORTING_SUMMARY)
    object_dashboard_service = _read(OBJECT_DASHBOARD_SERVICE)
    artifact_overview = _read(ARTIFACT_OVERVIEW)
    artifact_content = _read(ARTIFACT_CONTENT)
    artifact_hero = _read(ARTIFACT_HERO)
    artifact_signal_overview = _read(ARTIFACT_SIGNAL_OVERVIEW)
    artifact_reporting = _read(ARTIFACT_REPORTING)
    artifact_capacity = _read(ARTIFACT_CAPACITY)
    artifact_signals = _read(ARTIFACT_SIGNALS)
    artifact_operations = _read(ARTIFACT_OPERATIONS)
    artifact_provider_health = _read(ARTIFACT_PROVIDER_HEALTH)
    artifact_routes = _read(ARTIFACT_ROUTES)
    artifact_presentation = _read(ARTIFACT_PRESENTATION)
    page_hero = _read(PAGE_HERO)
    workspace_tabs = _read(WORKSPACE_TABS)
    dashboard_workspace = _read(DASHBOARD_WORKSPACE)
    reporting_workspace = _read(REPORTING_WORKSPACE)
    metric_card = _read(METRIC_CARD)
    tenant_setup_workspace = _read(TENANT_SETUP_WORKSPACE)
    kpi_cards = _read(KPI_CARDS)
    top_consumers = _read(TOP_CONSUMERS)
    routes = _read(ROUTES)
    service = _read(SERVICE)
    readme = _read(README)
    standard = _read(STANDARD)
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

    _verify_dashboard_hero_profile(hero, object_hero, page_hero)
    _verify_artifact_registry_dashboard(
        artifact_overview,
        artifact_content,
        artifact_hero,
        artifact_signal_overview,
        artifact_reporting,
        artifact_capacity,
        artifact_signals,
        artifact_operations,
        artifact_provider_health,
        artifact_routes,
        artifact_presentation,
    )
    _require(
        content,
        ('{% include "components/cluster/_onboarding_banner.html" %}',),
        'Kubernetes dashboard shared onboarding consumer',
    )
    for local_override in (
        'cluster_onboarding_steps =',
        'cluster_onboarding_action_url =',
        'cluster_onboarding_action_label =',
        'cluster_onboarding_action_icon =',
    ):
        if local_override in content:
            raise AssertionError(
                f'Kubernetes dashboard shared onboarding consumer: local semantic override is prohibited: {local_override}'
            )

    _require(
        onboarding_banner,
        (
            'blocked_state_steps = ["Open Cluster Integrations", "Register Cluster", "Run Sync"]',
            "blocked_state_action_url = url_for('integrations.kubernetes')",
            'blocked_state_action_label = "Open Cluster Integrations"',
            'blocked_state_action_icon = "plug-zap"',
            'blocked_state_permission = "clusters.manage"',
        ),
        'shared Kubernetes onboarding contract',
    )
    for stale_action in (
        "url_for('cluster.add_cluster')",
        'blocked_state_action_label = "Add Cluster"',
        '["Add Cluster", "Configure Integrations", "Run Sync"]',
    ):
        if stale_action in onboarding_banner:
            raise AssertionError(
                f'shared Kubernetes onboarding contract: stale direct-create onboarding remains: {stale_action}'
            )

    _require(
        content,
        (
            'components/operational_dashboard_workspace.html',
            'dashboard_workspace.controller(',
            'dashboard_workspace.navigation(',
            'dashboard_workspace.panel(',
            'import "components/peer_content_grid.html" as peer_content_grid',
            'peer_content_grid.layout_classes()',
            'hx-trigger="revealed"',
        ),
        'dashboard composition',
    )
    if content.count('dashboard_workspace.panel(') != 4:
        raise AssertionError('dashboard composition: expected four canonical framework panels')
    if content.count('peer_content_grid.layout_classes()') != 4:
        raise AssertionError('dashboard composition: expected four canonical peer-content grids')

    _require(
        object_content,
        (
            'storage/object_storage/dashboard/partials/_hero.html',
            'components/operational_dashboard_workspace.html',
            'dashboard_workspace.controller(',
            'dashboard_workspace.navigation(',
            'dashboard_workspace.panel(',
            'dashboard_workspace.standard_tabs',
            'hx-trigger="revealed"',
            'class="mt-5 space-y-5"',
        ),
        'Object Storage dashboard family composition',
    )

    _require(
        dashboard_workspace,
        (
            'data-kaori-dashboard-framework="operational-v1"',
            "('overview', 'Operations Overview', 'activity')",
            "('capacity', 'Capacity & Demand', 'gauge')",
            "('signals', 'Signals & Actions', 'bell-ring')",
            "('reporting', 'Reporting', 'file-text')",
            'workspace_tabs.render(standard_tabs',
            'moveTab(currentTab, direction, prefix)',
            "url.searchParams.set('tab', tab)",
            "window.history.replaceState({}, '', url)",
            'role="tabpanel"',
            'x-bind:hidden=',
        ),
        'shared operational dashboard workspace',
    )

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
            'hx-push-url="true"',
        ),
        'Kubernetes dashboard scope and signal wording',
    )
    _require(
        object_signal_overview,
        (
            'Operational Signal Overview',
            'System Signals Available',
            'Select a System for Detailed Signals',
            'hx-push-url="true"',
        ),
        'Object Storage dashboard scope and signal wording',
    )
    _require(
        tenant_setup_workspace,
        ('Tenant Governance Flow', 'components/numbered_governance_steps.html'),
        'Tenant Governance Flow shared numbered sequence',
    )
    for owner, source in (
        ('Kubernetes alert response guidance', alert_guidance),
        ('Object Storage alert response guidance', object_alert_guidance),
    ):
        _require(
            source,
            (
                'components/numbered_governance_steps.html',
                'alert_response_steps',
                'Controlled Response Flow',
                "'Validate'",
                "'Triage'",
                "'Investigate'",
                "'Respond'",
                "'Verify'",
                "'Record'",
            ),
            owner,
        )
        if 'components/operational_flow_steps.html' in source:
            raise AssertionError(f'{owner}: alert response must use the shared numbered governance sequence')

    for owner, source in (
        ('Kubernetes reporting guidance', reporting_guidance),
        ('Object Storage reporting guidance', object_reporting_guidance),
    ):
        _require(
            source,
            (
                'components/reporting_dashboard_workspace.html',
                'reporting_workspace.guidance(',
            ),
            owner,
        )

    _require(
        reporting_workspace,
        (
            'reporting_steps',
            'Reporting Workflow',
            'Scope Bound',
            'Evidence Backed',
            'Review First',
            'Governed Flow',
            'Execution Mode',
            "'Validate'",
            "'Select'",
            "'Create'",
            "'Generate'",
            "'Schedule'",
            "'Retain'",
            'Reporting Tip',
            'reporting.latest_reports[:4]',
        ),
        'shared reporting dashboard workspace',
    )
    for owner, source in (
        ('Kubernetes alert response guidance', alert_guidance),
        ('Object Storage alert response guidance', object_alert_guidance),
    ):
        _require(
            source,
            (
                'before acting on the signal',
                'establish an accountable owner',
                'remains auditable',
            ),
            f'{owner} detailed step copy',
        )
    _require(
        alert_summary,
        ('up to five recent cases', 'dashboard.alerts_snapshot.items[:5]'),
        'Kubernetes Alerts Summary preview',
    )
    _require(
        alerts_builder,
        ('for item in raw_items[:5]',),
        'Kubernetes Alerts Summary snapshot builder',
    )
    _require(
        object_alert_summary,
        ('up to five recent cases', 'dashboard.alerts.rows[:5]'),
        'Object Storage Alerts Summary preview',
    )
    _require(
        object_dashboard_service,
        ("for case in posture['cases'][:5]",),
        'Object Storage Alerts Summary snapshot builder',
    )
    for owner, source in (
        ('Kubernetes Alerts Summary template', alert_summary),
        ('Kubernetes Alerts Summary builder', alerts_builder),
        ('Object Storage Alerts Summary template', object_alert_summary),
        ('Object Storage Alerts Summary builder', object_dashboard_service),
    ):
        if '[:3]' in source and 'alert' in owner.lower():
            raise AssertionError(f'{owner}: stale three-record alert preview cap remains')

    _require(
        reporting_summary,
        ('reporting_workspace.summary(',),
        'Kubernetes Recent Report Activity consumer',
    )
    _require(
        reporting_builder,
        ('query_all(Report, selected_cluster_id, limit=4)',),
        'Kubernetes Recent Report Activity builder',
    )
    _require(
        object_reporting_summary,
        ('reporting_workspace.summary(',),
        'Object Storage Recent Report Activity consumer',
    )
    _require(
        reporting_workspace,
        ('reporting.latest_reports[:4]',),
        'shared Recent Report Activity preview',
    )
    _require(
        object_dashboard_service,
        ('recent = reports_query.order_by(Report.created_at.desc()).limit(4).all()',),
        'Object Storage Recent Report Activity builder',
    )
    for owner, source in (
        ('Kubernetes Reporting Summary', reporting_summary),
        ('Kubernetes Reporting builder', reporting_builder),
        ('Object Storage Reporting Summary', object_reporting_summary),
    ):
        if 'three latest generated' in source or 'limit=3' in source or '[:3]' in source:
            raise AssertionError(f'{owner}: stale three-record report preview cap remains')
    _require(
        object_alert_guidance,
        (
            'Developing capacity, request-path, or availability risk. Investigate before escalation.',
            'Low-risk operational signal. Validate relevance, recurrence, and scope.',
        ),
        'Object Storage compact alert guidance',
    )
    if reporting_workspace.index('Review First') >= reporting_workspace.index('Governed Flow'):
        raise AssertionError('shared reporting workspace must present review guardrails before the governed flow')

    for dashboard_dir in (DASHBOARD_DIR, OBJECT_DASHBOARD_DIR):
        dashboard_source = '\n'.join(path.read_text(encoding='utf-8') for path in sorted(dashboard_dir.rglob('*.html')))
        if 'What This Summary Means' in dashboard_source:
            raise AssertionError(f'{dashboard_dir.relative_to(ROOT)} still contains retired summary explanation')
        if 'text-[' in dashboard_source or 'tracking-[' in dashboard_source:
            raise AssertionError(f'{dashboard_dir.relative_to(ROOT)} contains arbitrary typography')
        for stale in STALE_COPY:
            if stale in dashboard_source:
                raise AssertionError(f'{dashboard_dir.relative_to(ROOT)} contains stale wording: {stale}')

    _require(
        metric_card,
        (
            "macro render(label, value, description, icon, source_label='Operational', scope_label='Active Scope')",
            'components/table_label.html',
            'components/table_primitives.html',
            'table_ui.block_classes()',
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
    if 'from Prometheus' in top_consumers:
        raise AssertionError('dashboard top-consumer presentation must use committed-snapshot wording')

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
    for token in (
        'kubernetes.client',
        'prometheus_api_client',
        'requests.get',
        'httpx.get',
        'boto3.client',
    ):
        if token in service or token in routes:
            raise AssertionError(f'dashboard web boundary contains live provider access: {token}')
    if '**_: Any' in service:
        raise AssertionError('dashboard service still exposes a compatibility catch-all argument')
    if 'live_cluster' in service or 'live_cluster' in schema or 'get_live_cluster' in utils:
        raise AssertionError('dashboard internals still use misleading live-cluster naming')
    kpi_schema = schema.split('class DashboardKpi:', 1)[1].split('@dataclass', 1)[0]
    if 'tone:' in kpi_schema or 'trend:' in kpi_schema or 'tone=' in kpi_builder:
        raise AssertionError('dashboard KPI model/builder still carries retired presentation fields')
    if 'build_hero_integration_meta' in freshness or 'build_hero_integration_meta' in sections_init:
        raise AssertionError('dashboard still contains orphan Hero integration metadata builder')
    if 'def format_gib' in utils:
        raise AssertionError('dashboard still contains unused duplicate format_gib helper')
    if 'returned by Prometheus' in top_consumers_source or 'Prometheus returned' in top_consumers_source:
        raise AssertionError('dashboard presentation still implies request-time Prometheus access')

    _require(
        readme,
        (
            'read-only operational projection over committed KAORI data',
            'OPERATIONAL_DASHBOARD.md` v1.7',
            'page_hero.operational_dashboard(...)',
            'keyboard navigation',
            'artifact-format neutral',
            'Web requests must not query Kubernetes, Metrics Source, or Alertmanager directly',
        ),
        'dashboard technical README',
    )
    _require(
        standard,
        (
            '# KAORI Operational Dashboard Pattern v1.7',
            'Operational Dashboard Hero Profile',
            'page_hero.operational_dashboard(...)',
            'Active Scope',
            'Data Authority',
            'Committed Snapshots',
            'Dashboard family consistency',
            'Identity → Scope → Indicators → Peer analysis → Interpretation → Action',
            'Web requests read committed database rows and worker snapshots only',
            'Layered release evidence',
            'Registry/Harbor',
            'Artifact Registry Overview',
            'Source Control/GitHub',
            'components/operational_dashboard_workspace.html',
            'components/reporting_dashboard_workspace.html',
            'components/numbered_governance_steps.html',
            'Arrow Left/Right wrap; Home selects first; End selects last;',
        ),
        'operational dashboard standard',
    )

    if 'python scripts/verify_operational_dashboard_standard.py' not in quality_gate:
        raise AssertionError('scripts/quality_gate.sh does not execute the dashboard standard verifier')
    if "-m 'not debug and not e2e and not contract and not migration'" not in quality_gate:
        raise AssertionError(
            'scripts/quality_gate.sh does not execute the canonical Dashboard functional release suite'
        )
    if "'tests/kubernetes/dashboard/test_kubernetes_dashboard_characterization.py': 7" not in feature_coverage:
        raise AssertionError('Dashboard behavioral characterization is not protected by feature coverage')
    for requirement in (
        "'tests/unit/kubernetes/dashboard/test_kubernetes_dashboard_domain.py': 3",
        "'tests/security/kubernetes/dashboard/test_kubernetes_dashboard_security.py': 3",
        "'tests/rendering/kubernetes/dashboard/test_kubernetes_dashboard_rendering.py': 2",
        "'tests/integration/kubernetes/dashboard/test_kubernetes_dashboard_repository.py': 1",
        "'tests/e2e/kubernetes/dashboard/test_kubernetes_dashboard_smoke.py': 2",
    ):
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
        raise AssertionError('Dashboard snapshot-flow tests still use retired scope contract')
    if (
        'lambda _models, _selected' in snapshot_flow_test
        or 'models, clusters, options, None, None' in snapshot_flow_test
    ):
        raise AssertionError('Dashboard snapshot-flow tests still target retired service helper signatures')

    print(
        'KAORI operational dashboard standard passed: shared Hero profile parity, canonical composition, '
        'snapshot-only web boundary, authorization-first lazy sections, URL-backed keyboard-accessible tabs, '
        'shared style ownership, Kubernetes/Object Storage references plus Artifact Registry conformance, '
        'shared dashboard/reporting frameworks, five-record alert previews, four-record report previews, '
        'behavioral release evidence, documentation, and quality-gate enforcement match v1.7.'
    )


if __name__ == '__main__':
    verify()
