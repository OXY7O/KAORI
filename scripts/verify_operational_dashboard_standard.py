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
RECOMMENDATIONS_BUILDER = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'sections' / 'recommendations.py'
OBJECT_DASHBOARD_DIR = ROOT / 'app' / 'templates' / 'storage' / 'object_storage' / 'dashboard'
OBJECT_CONTENT = OBJECT_DASHBOARD_DIR / 'partials' / '_content.html'
OBJECT_HERO = OBJECT_DASHBOARD_DIR / 'partials' / '_hero.html'
OBJECT_SIGNAL_OVERVIEW = OBJECT_DASHBOARD_DIR / 'partials' / '_signal_overview.html'
OBJECT_KPI_CARDS = OBJECT_DASHBOARD_DIR / 'partials' / '_kpi_cards.html'
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
ARTIFACT_KPI_CARDS = ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_kpi_cards.html'
ARTIFACT_REPORTING = ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_reporting.html'
ARTIFACT_CAPACITY = ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_capacity.html'
ARTIFACT_SIGNALS = ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_signals.html'
ARTIFACT_OPERATIONS = ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_operations.html'
ARTIFACT_PROVIDER_HEALTH = (
    ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_provider_health.html'
)
ARTIFACT_ROUTES = ROOT / 'app' / 'artifact_registry' / 'routes.py'
ARTIFACT_PRESENTATION = ROOT / 'app' / 'artifact_registry' / 'presentation.py'
ARTIFACT_PRESENTATION_COMMON = ROOT / 'app' / 'artifact_registry' / 'presentation_common.py'
ARTIFACT_PRESENTATION_OVERVIEW = ROOT / 'app' / 'artifact_registry' / 'presentation_overview.py'
OBJECT_ROUTES = ROOT / 'app' / 'storage' / 'object_storage' / 'dashboard' / 'routes.py'
DASHBOARD_APPLICATION_CONTRACT = ROOT / 'app' / 'dashboards' / 'common' / 'operational.py'
COMMON_PAGINATION = ROOT / 'app' / 'common' / 'pagination.py'
PAGE_HERO = ROOT / 'app' / 'templates' / 'components' / 'page_hero.html'
WORKSPACE_TABS = ROOT / 'app' / 'templates' / 'components' / 'workspace_tabs.html'
DASHBOARD_WORKSPACE = ROOT / 'app' / 'templates' / 'components' / 'operational_dashboard_workspace.html'
REPORTING_WORKSPACE = ROOT / 'app' / 'templates' / 'components' / 'reporting_dashboard_workspace.html'
METRIC_CARD = ROOT / 'app' / 'templates' / 'components' / 'operational_metric_card.html'
SIGNAL_OVERVIEW_WORKSPACE = ROOT / 'app' / 'templates' / 'components' / 'operational_signal_overview.html'
EVIDENCE_TILE = ROOT / 'app' / 'templates' / 'components' / 'operational_evidence_tile.html'
ALERT_SUMMARY_WORKSPACE = ROOT / 'app' / 'templates' / 'components' / 'operational_alert_summary.html'
ALERT_RESPONSE_WORKSPACE = ROOT / 'app' / 'templates' / 'components' / 'operational_alert_response.html'
RECOMMENDATION_CARDS = ROOT / 'app' / 'templates' / 'components' / 'operational_recommendation_cards.html'
DASHBOARD_EMPTY_STATE = ROOT / 'app' / 'templates' / 'components' / 'states' / '_empty_state.html'
DASHBOARD_LOADING = ROOT / 'app' / 'templates' / 'components' / 'operational_section_loading.html'
DASHBOARDS_README = ROOT / 'app' / 'dashboards' / 'README.md'
LEGACY_KUBERNETES_SECTION_LOADING = DASHBOARD_DIR / 'partials' / '_section_loading.html'
KUBERNETES_CAPACITY = DASHBOARD_DIR / 'partials' / '_capacity_snapshot.html'
KUBERNETES_FORECAST = DASHBOARD_DIR / 'partials' / '_forecast_risk.html'
OBJECT_CAPACITY = OBJECT_DASHBOARD_DIR / 'partials' / '_capacity.html'
OBJECT_FORECAST = OBJECT_DASHBOARD_DIR / 'partials' / '_forecast_risk.html'
KUBERNETES_OVERVIEW = DASHBOARD_DIR / 'partials' / '_overview.html'
KUBERNETES_CAPACITY_TAB = DASHBOARD_DIR / 'partials' / '_capacity.html'
KUBERNETES_SIGNALS_TAB = DASHBOARD_DIR / 'partials' / '_signals.html'
KUBERNETES_REPORTING_TAB = DASHBOARD_DIR / 'partials' / '_reporting.html'
KUBERNETES_INVENTORY = DASHBOARD_DIR / 'partials' / '_inventory_summary.html'
KUBERNETES_FRESHNESS = DASHBOARD_DIR / 'partials' / '_data_freshness.html'
OBJECT_OVERVIEW = OBJECT_DASHBOARD_DIR / 'partials' / '_overview.html'
ARTIFACT_ALERT_SUMMARY = ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_alerts_summary.html'
ARTIFACT_ALERT_GUIDANCE = (
    ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_alert_response_guidance.html'
)
ARTIFACT_RECOMMENDATIONS = (
    ROOT / 'app' / 'templates' / 'artifact_registry' / 'partials' / '_overview_recommended_actions.html'
)
TENANT_SETUP_WORKSPACE = (
    ROOT / 'app' / 'templates' / 'kubernetes' / 'tenant' / 'partials' / '_tenant_setup_workspace.html'
)
KPI_CARDS = DASHBOARD_DIR / 'partials' / '_kpi_cards.html'
TOP_CONSUMERS = DASHBOARD_DIR / 'partials' / '_top_consumers.html'
CLUSTER_HEALTH_BUILDER = ROOT / 'app' / 'kubernetes' / 'dashboard' / 'sections' / 'cluster_health.py'
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
            "'Open Object Storage Integrations'",
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
    kpi_cards: str,
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
            'components/operational_signal_overview.html',
            'signal_overview.render(',
            "section='kpi_cards'",
            'hx-trigger="load"',
            'provider_id',
            'hx-push-url="true"',
            'hx-include="#artifact-registry-dashboard-active-tab"',
            'All Registry Providers',
        ),
        'Artifact Registry scope and signal overview',
    )
    _require(
        kpi_cards,
        (
            'components/operational_metric_card.html',
            "scope_label='Active Scope'",
            'data-kaori-artifact-registry-operational-kpis',
        ),
        'Artifact Registry bounded KPI projection',
    )
    _require(
        operations,
        (
            'artifact_registry/partials/_overview_provider_health.html',
            'Inventory Snapshot',
            'Data Freshness',
        ),
        'Artifact Registry Operations Overview parity',
    )
    for retired_action in (
        "current_user.has_permission('artifact_registry.sync')",
        "url_for('artifact_registry.sync_inventory')",
        'Sync Inventory',
    ):
        if retired_action in operations:
            raise AssertionError(
                f'Artifact Registry Operational Dashboard retains dashboard-local sync action: {retired_action}'
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
            '{% if not overview.selected_provider %}',
            'components/states/_blocked_state.html',
            'Select Registry Provider',
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
            'def _overview_scope_context(',
            'def _overview_kpi_values(',
            'def _overview_operations_projection(',
            'def _overview_capacity_projection(',
            'def build_overview_section(',
            "if section == 'kpi_cards':",
            "if section == 'provider_health':",
            "if section == 'overview':",
            "if section == 'capacity':",
            "if section == 'signals':",
            "if section == 'reporting':",
            'RegistryProject.integration_instance_id == selected_provider.id',
            'registry_metrics_readiness(provider)',
            "'scope_label': scope_label",
            "'capacity': capacity",
            "'alerts': _registry_alerts(selected_provider)",
            "'recommended_actions': _registry_recommended_actions(selected_provider)",
            "'reporting': _registry_reporting(selected_provider)",
            "'label': 'Inventory Snapshot'",
            "'label': 'Metrics Snapshot'",
            "'label': 'Security Snapshot'",
            "'label': 'Analytics Snapshot'",
            "'kpis': [",
            'func.count(RegistryArtifact.id)',
            'func.sum(RegistryArtifact.size_bytes)',
        ),
        'Artifact Registry committed bounded dashboard projection',
    )
    shell_projection = presentation.split('def build_overview(', 1)[1].split('def build_overview_section(', 1)[0]
    for forbidden in (
        'RegistryProject.query',
        'RegistryRepository.query',
        'RegistryArtifact.query',
        'RegistryTag.query',
        '_registry_capacity_views(',
        '_registry_alerts(',
        '_registry_recommended_actions(',
        '_registry_reporting(',
    ):
        if forbidden in shell_projection:
            raise AssertionError(f'Artifact Registry Fast Shell contains unrelated projection work: {forbidden}')
    for token in (
        'HarborClient(',
        'requests.get',
        'httpx.get',
    ):
        if token in routes or token in presentation:
            raise AssertionError(f'Artifact Registry dashboard web boundary contains live provider access: {token}')


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
    recommendations_builder = _read(RECOMMENDATIONS_BUILDER)
    object_content = _read(OBJECT_CONTENT)
    object_hero = _read(OBJECT_HERO)
    object_signal_overview = _read(OBJECT_SIGNAL_OVERVIEW)
    object_kpi_cards = _read(OBJECT_KPI_CARDS)
    object_alert_summary = _read(OBJECT_ALERT_SUMMARY)
    object_alert_guidance = _read(OBJECT_ALERT_GUIDANCE)
    object_reporting_guidance = _read(OBJECT_REPORTING_GUIDANCE)
    object_reporting_summary = _read(OBJECT_REPORTING_SUMMARY)
    object_dashboard_service = _read(OBJECT_DASHBOARD_SERVICE)
    artifact_overview = _read(ARTIFACT_OVERVIEW)
    artifact_content = _read(ARTIFACT_CONTENT)
    artifact_hero = _read(ARTIFACT_HERO)
    artifact_signal_overview = _read(ARTIFACT_SIGNAL_OVERVIEW)
    artifact_kpi_cards = _read(ARTIFACT_KPI_CARDS)
    artifact_reporting = _read(ARTIFACT_REPORTING)
    artifact_capacity = _read(ARTIFACT_CAPACITY)
    artifact_signals = _read(ARTIFACT_SIGNALS)
    artifact_operations = _read(ARTIFACT_OPERATIONS)
    artifact_provider_health = _read(ARTIFACT_PROVIDER_HEALTH)
    artifact_routes = _read(ARTIFACT_ROUTES)
    artifact_presentation = '\n'.join(
        (
            _read(ARTIFACT_PRESENTATION),
            _read(ARTIFACT_PRESENTATION_COMMON),
            _read(ARTIFACT_PRESENTATION_OVERVIEW),
        )
    )
    object_routes = _read(OBJECT_ROUTES)
    dashboard_application_contract = _read(DASHBOARD_APPLICATION_CONTRACT)
    common_pagination = _read(COMMON_PAGINATION)
    page_hero = _read(PAGE_HERO)
    workspace_tabs = _read(WORKSPACE_TABS)
    dashboard_workspace = _read(DASHBOARD_WORKSPACE)
    reporting_workspace = _read(REPORTING_WORKSPACE)
    metric_card = _read(METRIC_CARD)
    signal_overview_workspace = _read(SIGNAL_OVERVIEW_WORKSPACE)
    evidence_tile = _read(EVIDENCE_TILE)
    alert_summary_workspace = _read(ALERT_SUMMARY_WORKSPACE)
    alert_response_workspace = _read(ALERT_RESPONSE_WORKSPACE)
    recommendation_cards = _read(RECOMMENDATION_CARDS)
    dashboard_empty_state = _read(DASHBOARD_EMPTY_STATE)
    dashboard_loading = _read(DASHBOARD_LOADING)
    dashboards_readme = _read(DASHBOARDS_README)
    kubernetes_capacity = _read(KUBERNETES_CAPACITY)
    kubernetes_forecast = _read(KUBERNETES_FORECAST)
    object_capacity = _read(OBJECT_CAPACITY)
    object_forecast = _read(OBJECT_FORECAST)
    kubernetes_overview = _read(KUBERNETES_OVERVIEW)
    kubernetes_capacity_tab = _read(KUBERNETES_CAPACITY_TAB)
    kubernetes_signals_tab = _read(KUBERNETES_SIGNALS_TAB)
    kubernetes_reporting_tab = _read(KUBERNETES_REPORTING_TAB)
    kubernetes_inventory = _read(KUBERNETES_INVENTORY)
    kubernetes_freshness = _read(KUBERNETES_FRESHNESS)
    object_overview = _read(OBJECT_OVERVIEW)
    artifact_alert_summary = _read(ARTIFACT_ALERT_SUMMARY)
    artifact_alert_guidance = _read(ARTIFACT_ALERT_GUIDANCE)
    artifact_recommendations = _read(ARTIFACT_RECOMMENDATIONS)
    tenant_setup_workspace = _read(TENANT_SETUP_WORKSPACE)
    kpi_cards = _read(KPI_CARDS)
    top_consumers = _read(TOP_CONSUMERS)
    cluster_health_builder = _read(CLUSTER_HEALTH_BUILDER)
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
        artifact_kpi_cards,
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
            'provider_prerequisite_steps = ["Open Cluster Integrations", "Register Cluster", "Run Sync"]',
            "provider_prerequisite_action_url = url_for('integrations.kubernetes')",
            'provider_prerequisite_action_label = "Open Cluster Integrations"',
            'provider_prerequisite_action_icon = "plug-zap"',
            'provider_prerequisite_permission = "clusters.manage"',
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
            'components/operational_section_loading.html',
            'dashboard_workspace.controller(',
            'dashboard_workspace.navigation(',
            'dashboard_workspace.panel(',
            'dashboard_workspace.standard_tabs',
            "url_for('kubernetes_dashboard.section', section=tab_key)",
            'section_loading.section(',
            'hx-trigger="revealed"',
            'class="mt-5 space-y-5"',
        ),
        'dashboard composition',
    )
    if content.count('dashboard_workspace.panel(') != 1:
        raise AssertionError('dashboard composition: expected one loop-owned canonical framework panel')
    for owner, source, requirements in (
        (
            'Kubernetes Operations Overview',
            kubernetes_overview,
            (
                'components/peer_content_grid.html',
                'kubernetes/dashboard/partials/_cluster_health.html',
                'kubernetes/dashboard/partials/_inventory_summary.html',
                'kubernetes/dashboard/partials/_data_freshness.html',
            ),
        ),
        (
            'Kubernetes Capacity & Demand',
            kubernetes_capacity_tab,
            (
                'components/peer_content_grid.html',
                'kubernetes/dashboard/partials/_capacity_snapshot.html',
                'kubernetes/dashboard/partials/_forecast_risk.html',
                'kubernetes/dashboard/partials/_top_consumers.html',
            ),
        ),
        (
            'Kubernetes Signals & Actions',
            kubernetes_signals_tab,
            (
                'components/peer_content_grid.html',
                'kubernetes/dashboard/partials/_alerts_summary.html',
                'kubernetes/dashboard/partials/_alert_response_guidance.html',
                'kubernetes/dashboard/partials/_recommended_actions.html',
            ),
        ),
        (
            'Kubernetes Reporting',
            kubernetes_reporting_tab,
            (
                'components/peer_content_grid.html',
                'kubernetes/dashboard/partials/_reporting_summary.html',
                'kubernetes/dashboard/partials/_reporting_guidance.html',
            ),
        ),
    ):
        _require(source, requirements, owner)

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
        dashboard_loading,
        (
            'components/operational_section_card.html',
            "table_label.status_indicator_label('Preparing', 'pending')",
            '{% macro section(',
            '{% macro kpis(',
            'aria-busy="true"',
            'h-14 animate-pulse rounded-lg bg-surface-hover',
            'h-28 animate-pulse rounded-lg bg-surface-hover',
        ),
        'shared Operational Dashboard loading presentation',
    )
    for owner, section_source, signal_source in (
        ('Kubernetes dashboard', content, signal_overview),
        ('Object Storage dashboard', object_content, object_signal_overview),
        ('Artifact Registry dashboard', artifact_content, artifact_signal_overview),
    ):
        _require(
            section_source,
            (
                'components/operational_section_loading.html',
                'section_loading.section(',
                'hx-trigger="revealed"',
                'hx-target="this"',
                'hx-swap="outerHTML"',
            ),
            f'{owner} bounded section loading',
        )
        _require(
            signal_source,
            (
                'components/operational_section_loading.html',
                'section_loading.kpis(',
                'hx-trigger="load"',
                'hx-target="this"',
                'hx-swap="outerHTML"',
            ),
            f'{owner} KPI loading',
        )
        if '<div class="grid gap-3 sm:grid-cols-3" aria-busy="true">' in section_source:
            raise AssertionError(f'{owner}: duplicates canonical section loading skeleton')
        if 'for _ in range(4)' in signal_source:
            raise AssertionError(f'{owner}: duplicates canonical KPI loading skeleton')
    if 'item_count=8' not in signal_overview:
        raise AssertionError('Kubernetes dashboard KPI loader must represent eight indicators')
    for owner, signal_source in (
        ('Object Storage dashboard', object_signal_overview),
        ('Artifact Registry dashboard', artifact_signal_overview),
    ):
        if 'item_count=4' not in signal_source:
            raise AssertionError(f'{owner}: KPI loader must represent four indicators')
    if LEGACY_KUBERNETES_SECTION_LOADING.exists():
        raise AssertionError('Kubernetes dashboard retains retired page-local _section_loading.html')
    _require(
        dashboards_readme,
        (
            'operational_section_loading.html',
            'section_loading.kpis(...)',
            'section_loading.section(...)',
            'hx-trigger="load"',
            'hx-trigger="revealed"',
            'Projection granularity stays domain-owned',
        ),
        'Operational Dashboard technical loading contract',
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
    _require(
        alert_response_workspace,
        (
            'components/numbered_governance_steps.html',
            'components/operational_callout.html',
            'Controlled Response Flow',
            'numbered_steps.render(steps, flow_aria_label)',
        ),
        'shared alert response workspace',
    )
    for owner, source in (
        ('Kubernetes alert response guidance', alert_guidance),
        ('Object Storage alert response guidance', object_alert_guidance),
        ('Artifact Registry alert response guidance', artifact_alert_guidance),
    ):
        _require(
            source,
            (
                'components/operational_alert_response.html',
                'alert_response_steps',
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
            raise AssertionError(f'{owner}: alert response must not own a local operational-flow variant')

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
        alert_summary_workspace,
        (
            'macro render(',
            'rows[:5]',
            'data-kaori-alert-insight="stacked"',
            'data-kaori-alert-insight-metrics="dedicated-row"',
            'Open Alert Intelligence',
            'alert.title',
            'alert.description',
            'alert.severity',
            'alert.state',
            'alert.age',
        ),
        'shared Alerts Summary workspace',
    )
    for retired in (
        'row_title_key',
        'row_description_key',
        'row_severity_key',
        'row_state_key',
        'row_age_key',
        'row_age_datetime',
    ):
        if retired in alert_summary_workspace:
            raise AssertionError(f'shared Alerts Summary retains domain adapter API: {retired}')
    for owner, source, row_token in (
        ('Kubernetes Alerts Summary', alert_summary, 'rows=dashboard.alerts_snapshot.items'),
        ('Object Storage Alerts Summary', object_alert_summary, 'rows=dashboard.alerts.rows'),
        ('Artifact Registry Alerts Summary', artifact_alert_summary, 'rows=overview.alerts.rows'),
    ):
        _require(
            source,
            (
                'components/operational_alert_summary.html',
                'alert_summary.render(',
                'up to five recent',
                row_token,
            ),
            owner,
        )
    _require(
        alerts_builder,
        ('for item in raw_items[:5]',),
        'Kubernetes Alerts Summary snapshot builder',
    )
    _require(
        service,
        ('for case in cases[:5]',),
        'Kubernetes Alert Intelligence dashboard preview',
    )
    _require(
        object_dashboard_service,
        ("for case in posture['cases'][:5]",),
        'Object Storage Alerts Summary snapshot builder',
    )
    for owner, source in (
        ('shared Alerts Summary template', alert_summary_workspace),
        ('Kubernetes Alerts Summary builder', alerts_builder),
        ('Kubernetes dashboard service', service),
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
            'Emerging capacity or availability risk.',
            'Low-risk operational signal. Validate relevance, recurrence, and scope.',
        ),
        'Object Storage compact alert guidance',
    )
    _require(
        signal_overview_workspace,
        (
            'Operational Signal Overview',
            'Active Scope',
            'selector_html|safe',
            '{% set signal_content = caller() %}',
            'signal_content|safe',
        ),
        'shared Operational Signal Overview',
    )
    caller_capture = signal_overview_workspace.find('{% set signal_content = caller() %}')
    section_call = signal_overview_workspace.find('{% call operational_section_card.render(')
    if caller_capture < 0 or section_call < 0 or caller_capture >= section_call:
        raise AssertionError(
            'shared Operational Signal Overview must capture the outer caller before entering the nested section-card call'
        )
    if signal_overview_workspace.count('caller()') != 1:
        raise AssertionError(
            'shared Operational Signal Overview must not invoke caller() inside the nested section-card call scope'
        )
    for owner, source in (
        ('Kubernetes Operational Signal Overview', signal_overview),
        ('Object Storage Operational Signal Overview', object_signal_overview),
        ('Artifact Registry Operational Signal Overview', artifact_signal_overview),
    ):
        _require(
            source,
            ('components/operational_signal_overview.html', 'signal_overview.render('),
            owner,
        )
    _require(
        evidence_tile,
        ('macro snapshot(', 'macro freshness(', 'components/table_label.html'),
        'shared Operational Dashboard evidence tiles',
    )
    for owner, source in (
        ('Kubernetes Inventory Snapshot', kubernetes_inventory),
        ('Kubernetes Data Freshness', kubernetes_freshness),
        ('Object Storage Operations Overview', object_overview),
        ('Artifact Registry Operations Overview', artifact_operations),
    ):
        _require(source, ('components/operational_evidence_tile.html', 'evidence_tile.'), owner)
    _require(
        dashboard_empty_state,
        (
            "state_variant == 'panel'",
            'border border-dashed border-outline-default',
            'data-kaori-empty-state',
        ),
        'shared Operational Dashboard dashed panel empty state',
    )
    for owner, source in (
        ('Kubernetes Capacity Snapshot empty evidence', kubernetes_capacity),
        ('Kubernetes Forecast empty evidence', kubernetes_forecast),
        ('Object Storage Capacity Snapshot empty evidence', object_capacity),
        ('Object Storage Forecast empty evidence', object_forecast),
        ('Kubernetes Alert Response empty evidence', alert_guidance),
        ('Object Storage Alert Response empty evidence', object_alert_guidance),
        ('Artifact Registry Alert Response empty evidence', artifact_alert_guidance),
    ):
        _require(
            source,
            (
                'components/states/_empty_state.html',
                'empty_state_variant = "panel"',
            ),
            owner,
        )

    _require(
        alert_summary_workspace,
        (
            '{% elif not source_available %}',
            '{% elif total_alerts == 0 %}',
            'components/states/_empty_state.html',
            'empty_state_variant = "panel"',
            'empty_state_min_height = "min-h-[220px]"',
        ),
        'shared Alerts Summary dashed empty evidence',
    )
    unavailable_alert_branch = alert_summary_workspace.split('{% elif not source_available %}', 1)[1].split(
        '{% elif total_alerts == 0 %}', 1
    )[0]
    if 'components/states/_blocked_state.html' in unavailable_alert_branch:
        raise AssertionError('shared Alerts Summary source-unavailable evidence must use dashed empty-state panel')

    _require(
        recommendation_cards,
        (
            'macro render(',
            "'Recommended Actions'",
            'intelligence.recommendation_details',
            'normalized_priority',
            'No Active Recommendations',
        ),
        'shared Operational Dashboard recommendation cards',
    )
    if 'action.href' in recommendation_cards:
        raise AssertionError('shared recommendation renderer must own the canonical Intelligence destination')
    _require(
        recommendations_builder,
        (
            'title=',
            'description=',
            'category=',
            'severity=',
            'icon=',
            'priority=',
            'source=',
            'rule_key=',
        ),
        'Kubernetes recommendation projection',
    )
    if 'href=' in recommendations_builder or 'href: str' in schema or 'recommendation_href' in utils:
        raise AssertionError('Kubernetes recommendation projection retains a domain-local destination')
    for owner, source in (
        ('Object Storage alert projection', object_dashboard_service),
        ('Artifact Registry alert projection', artifact_presentation),
    ):
        _require(source, ("'title':", "'description':", "'severity':", "'state':", "'age':"), owner)
    for owner, source in (
        ('Kubernetes Recommended Actions', _read(DASHBOARD_DIR / 'partials' / '_recommended_actions.html')),
        ('Object Storage Recommended Actions', _read(OBJECT_DASHBOARD_DIR / 'partials' / '_recommended_actions.html')),
        ('Artifact Registry Recommended Actions', artifact_recommendations),
    ):
        _require(
            source,
            ('components/operational_recommendation_cards.html', 'recommendation_cards.render('),
            owner,
        )
    if "operational_callout.render('Capacity Action Flow'" in kubernetes_capacity:
        raise AssertionError('Kubernetes Capacity retains redundant Capacity Action Flow callout')
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
    for owner, source in (
        ('Kubernetes Operational Signal KPI cards', kpi_cards),
        ('Object Storage Operational Signal KPI cards', object_kpi_cards),
        ('Artifact Registry Operational Signal KPI cards', artifact_kpi_cards),
    ):
        _require(source, ("scope_label='Active Scope'",), owner)
    for owner, source in (
        ('Kubernetes Operational Signal KPI cards', kpi_cards),
        ('Object Storage Operational Signal KPI cards', object_kpi_cards),
        ('Artifact Registry Operational Signal KPI cards', artifact_signal_overview),
    ):
        for retired_scope in (
            'scope_label=overview.scope_label',
            "scope_label='Selected System'",
            "scope_label='Fleet'",
            'scope_label=scope_label',
        ):
            if retired_scope in source:
                raise AssertionError(f'{owner}: dynamic KPI scope badge remains: {retired_scope}')

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

    shared_section_owner = {
        '_signal_overview.html': 'components/operational_signal_overview.html',
        '_alerts_summary.html': 'components/operational_alert_summary.html',
        '_recommended_actions.html': 'components/operational_recommendation_cards.html',
        '_alert_response_guidance.html': 'components/operational_alert_response.html',
    }
    for name in SECTION_PARTIALS:
        source = _read(DASHBOARD_DIR / 'partials' / name)
        if name in shared_section_owner:
            _require(source, (shared_section_owner[name],), f'dashboard section {name}')
        else:
            _require(
                source,
                ('components/operational_section_card.html', 'operational_section_card.render('),
                f'dashboard section {name}',
            )

    _verify_route_authorization_order(routes)
    _require(
        dashboard_application_contract,
        (
            'OPERATIONAL_DASHBOARD_TABS: tuple[str, ...] = (',
            "'overview'",
            "'capacity'",
            "'signals'",
            "'reporting'",
            'DASHBOARD_PAGE_SIZES = PER_PAGE_OPTIONS',
            'normalize_operational_tab',
            'normalize_dashboard_page_size',
            'is_htmx_request',
        ),
        'shared Operational Dashboard application contract',
    )
    _require(
        common_pagination,
        (
            'DEFAULT_PER_PAGE = 5',
            'PER_PAGE_OPTIONS: tuple[int, ...] = (5, 10, 25, 50)',
            'def normalize_per_page(',
        ),
        'canonical pagination contract',
    )
    for owner, source in (
        ('Kubernetes dashboard routes', routes),
        ('Object Storage dashboard routes', object_routes),
        ('Artifact Registry dashboard routes', artifact_routes),
    ):
        _require(
            source,
            (
                'normalize_operational_tab',
                'normalize_dashboard_page_size',
            ),
            owner,
        )
        for stale in (
            "DASHBOARD_TABS = {'overview', 'capacity', 'signals', 'reporting'}",
            '_PAGE_SIZES = {5, 10, 25, 50}',
            'def _active_tab(',
            'def _cluster_health_per_page(',
            '_cluster_health_per_page()',
            'def _system_health_per_page(',
            '_system_health_per_page()',
            'def _provider_health_per_page(',
            '_provider_health_per_page()',
        ):
            if stale in source:
                raise AssertionError(f'{owner}: local dashboard application contract remains: {stale}')
    for owner, source in (
        ('Kubernetes dashboard routes', routes),
        ('Object Storage dashboard routes', object_routes),
    ):
        _require(source, ('is_htmx_request(request.headers)',), f'{owner} shared HTMX request contract')
    _require(
        routes,
        (
            "@permission_required('dashboard.view')",
            'SECTION_TEMPLATES = {',
            "'overview': 'kubernetes/dashboard/partials/_overview.html'",
            "'capacity': 'kubernetes/dashboard/partials/_capacity.html'",
            "'signals': 'kubernetes/dashboard/partials/_signals.html'",
            "'reporting': 'kubernetes/dashboard/partials/_reporting.html'",
            'if has_registered_clusters() is False:',
            "cluster_health_per_page=normalize_dashboard_page_size(request.args.get('cluster_health_per_page'))",
        ),
        'Kubernetes dashboard route boundary',
    )
    _require(
        object_routes,
        ("system_health_per_page=normalize_dashboard_page_size(request.args.get('system_health_per_page'))",),
        'Object Storage dashboard section pagination contract',
    )
    _require(
        artifact_routes,
        ("provider_health_per_page=normalize_dashboard_page_size(request.args.get('provider_health_per_page'))",),
        'Artifact Registry dashboard section pagination contract',
    )
    _require(
        artifact_presentation,
        ('normalize_operational_tab(active_tab)',),
        'Artifact Registry dashboard tab normalization',
    )
    _require(
        service,
        (
            'database-only dashboard shell',
            'Build one bounded dashboard projection from committed KAORI state.',
            "if section == 'overview':",
            "if section == 'capacity':",
            "if section == 'signals':",
            "if section == 'reporting':",
            'def _populate_cluster_health(',
            'def _populate_data_freshness(',
            'def _populate_capacity(',
            'def _populate_signals(',
            'read_dashboard_snapshot(',
            'query_for_clusters(',
            'paginate_sequence(',
        ),
        'dashboard service boundary',
    )
    freshness_projection = service.split('def _populate_data_freshness(', 1)[1].split('def _populate_capacity(', 1)[0]
    for broad_builder in (
        '_capacity_signal(',
        '_alerts_signal(',
        '_top_consumers_signal(',
        '_forecast_signal(',
        'build_reporting_snapshot(',
    ):
        if broad_builder in freshness_projection:
            raise AssertionError(f'Kubernetes Data Freshness rebuilds unrelated presentation evidence: {broad_builder}')
    _require(
        service,
        ('from app.common.pagination import paginate_sequence',),
        'Kubernetes canonical pagination consumer',
    )
    for stale in (
        'def _normalize_page_number(',
        'def paginate_sequence(',
        'ClusterHealthPagination',
    ):
        if stale in cluster_health_builder or stale in schema:
            raise AssertionError(f'Kubernetes Cluster Health retains local pagination mechanics: {stale}')
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
            'Operational Signal KPI cards use the fixed context badge **Active Scope**',
            'job initiation and mutation controls such as inventory synchronization do not render inside dashboard KPI or evidence cards',
            'Data Authority',
            'Committed Snapshots',
            'Dashboard family consistency',
            'Identity → Scope → Indicators → Peer analysis → Interpretation → Action',
            'Web requests read committed database rows and worker snapshots only',
            'Layered release evidence',
            'Registry/Harbor',
            'Artifact Registry Overview',
            'Source Control/GitHub',
            'app/dashboards/common/operational.py',
            'app/common/pagination.py',
            'components/operational_dashboard_workspace.html',
            'components/operational_signal_overview.html',
            'components/operational_evidence_tile.html',
            'components/operational_alert_summary.html',
            'components/operational_alert_response.html',
            'components/operational_recommendation_cards.html',
            'components/operational_section_loading.html',
            'components/reporting_dashboard_workspace.html',
            'components/numbered_governance_steps.html',
            'Section-local missing, unavailable, not-materialized, no-findings, or no-active-signal evidence in **Capacity & Demand** and **Signals & Actions** uses',
            'Arrow Left/Right wrap; Home selects first; End selects last;',
            'Fast Shell & Bounded Section Loading',
            '1 HTTP request → 1 bounded presentation projection',
            'All dashboard loading placeholders use `components/operational_section_loading.html`',
            'Projection granularity remains domain-owned',
            'Section requests must not call a full-dashboard builder',
            'Do not materialize full ORM collections',
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
            'test_authorized_operations_overview_uses_one_canonical_tab_projection',
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
        'shared application/presentation/reporting contracts, five-record alert previews, four-record report previews, '
        'behavioral release evidence, documentation, and quality-gate enforcement match v1.7.'
    )


if __name__ == '__main__':
    verify()
