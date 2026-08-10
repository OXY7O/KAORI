from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT / 'app' / 'templates' / 'dashboards' / 'kubernetes'
CONTENT = DASHBOARD_DIR / 'partials' / '_content.html'
SIGNAL_OVERVIEW = DASHBOARD_DIR / 'partials' / '_signal_overview.html'
REPORTING_GUIDANCE = DASHBOARD_DIR / 'partials' / '_reporting_guidance.html'
WORKSPACE_TABS = ROOT / 'app' / 'templates' / 'components' / 'workspace_tabs.html'
METRIC_CARD = ROOT / 'app' / 'templates' / 'components' / 'operational_metric_card.html'
KPI_CARDS = DASHBOARD_DIR / 'partials' / '_kpi_cards.html'
TOP_CONSUMERS = DASHBOARD_DIR / 'partials' / '_top_consumers.html'
ROUTES = ROOT / 'app' / 'dashboards' / 'kubernetes' / 'routes.py'
SERVICE = ROOT / 'app' / 'dashboards' / 'kubernetes' / 'service.py'
README = ROOT / 'app' / 'dashboards' / 'kubernetes' / 'README.md'
STANDARD = ROOT / 'docs' / 'design' / 'patterns' / 'OPERATIONAL_DASHBOARD.md'
AUDIT = ROOT / 'docs' / 'design' / 'audits' / 'KUBERNETES_OPERATIONS_DASHBOARD_ALIGNMENT_AUDIT_2026_08.md'
QUALITY_GATE = ROOT / 'scripts' / 'quality_gate.sh'

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


def verify() -> None:
    content = _read(CONTENT)
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

    _require(
        routes,
        (
            "@permission_required('dashboard.view')",
            "DASHBOARD_TABS = {'overview', 'capacity', 'signals', 'reporting'}",
            'CLUSTER_HEALTH_PAGE_SIZES = {5, 10, 25, 50}',
            'SECTION_TEMPLATES = {',
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

    _require(
        readme,
        (
            'read-only operational projection over committed KAORI data',
            'OPERATIONAL_DASHBOARD.md` v1.1',
            'Arrow Left/Right, Home, and End keyboard navigation',
            'artifact-format neutral',
            'Web requests must not query Kubernetes, Prometheus, or Alertmanager directly',
        ),
        'dashboard technical README',
    )

    _require(
        standard,
        (
            '# KAORI Operational Dashboard Pattern v1.1',
            '**Status:** Locked reference pattern',
            'Kubernetes Operations Dashboard',
            'Identity → Scope → Indicators → Peer analysis → Interpretation → Action',
            'Web requests read committed database rows and worker snapshots only',
            'Arrow Left/Right wrap through tabs',
            'Select a Cluster for Detailed Signals',
            'Reporting guidance must remain format-neutral',
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
            'Technical risks retained for separate work',
        ),
        'dashboard alignment audit',
    )

    if 'python scripts/verify_operational_dashboard_standard.py' not in quality_gate:
        raise AssertionError('scripts/quality_gate.sh does not execute the dashboard standard verifier')

    print(
        'KAORI operational dashboard standard passed: canonical composition, snapshot-only web boundary, '
        'URL-backed keyboard-accessible tabs, shared style ownership, format-neutral reporting guidance, '
        'top-consumer snapshot semantics, documentation, audit, and quality-gate enforcement match v1.1.'
    )


if __name__ == '__main__':
    verify()
