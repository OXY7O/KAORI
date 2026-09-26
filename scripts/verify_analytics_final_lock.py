#!/usr/bin/env python3
"""Verify Kubernetes Analytics final-recheck runtime, UI, security, and release contracts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYTICS_TEMPLATES = ROOT / 'app/templates/analytics'
ROUTE_FILES = tuple(sorted((ROOT / 'app/kubernetes/analytics').glob('*/routes.py'))) + (
    ROOT / 'app/storage/object_storage/analytics/routes.py',
    ROOT / 'app/analytics/routes.py',
)
RELEASE_EVIDENCE = (
    'tests/contracts/analytics/test_analytics_final_release_contract.py',
    'tests/unit/kubernetes/analytics/test_materialization_identity.py',
    'tests/kubernetes/analytics/test_kubernetes_analytics_page_flows.py',
    'tests/security/kubernetes/analytics/test_analytics_security.py',
    'tests/rendering/kubernetes/analytics/test_analytics_rendering.py',
    'tests/integration/kubernetes/analytics/test_materialized_snapshot_read_model.py',
    'tests/e2e/kubernetes/analytics/test_analytics_smoke.py',
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    runtime = read('app/static/js/analytics/controls.js')
    shared_tabs = read('app/templates/components/content_tabs.html')
    workspace = read('app/templates/kubernetes/analytics/components/_analysis_workspace.html')
    overview = read('app/templates/kubernetes/analytics/overview/index.html')
    top_consumers = read('app/templates/kubernetes/analytics/top_consumers/partials/_top_consumers_section.html')
    top_consumer_summary = read('app/templates/kubernetes/analytics/top_consumers/partials/_summary.html')
    record_detail_modal = read('app/templates/kubernetes/analytics/components/_record_detail_modal.html')
    forecast_index = read('app/templates/kubernetes/analytics/forecast/index.html')
    forecast_hero = read('app/templates/kubernetes/analytics/forecast/partials/_hero.html')
    quality_gate = read('scripts/quality_gate.sh')
    coverage = read('scripts/verify_feature_test_coverage.py')
    analytics_readme = read('app/kubernetes/analytics/README.md')
    tracker = read('docs/reviews/2026-08-10-final-recheck.md')
    content_tabs_standard = read('docs/design/components/CONTENT_TABS.md')
    tab_registry = read('docs/design/components/TAB_STYLES.md')

    for token in (
        'function setAnalyticsTab(tabset, tabId',
        "event.target.closest?.('[data-analytics-tab-button]')",
        'panel.hidden = panel.dataset.analyticsTabPanel !== tabId',
        "url.searchParams.set('tab', tabId)",
        "window.history.replaceState({}, '', url)",
        "window.htmx.trigger(target, 'kaori:analytics-tab-activated')",
        "['ArrowLeft', 'ArrowRight', 'Home', 'End']",
        'analyticsTabStorageKey(tabsetId)',
        "tabStateClasses(button, 'active')",
    ):
        require(token in runtime, f'Analytics native tab runtime missing: {token}', errors)

    require(
        'data-kaori-tab-active-classes' in shared_tabs and 'data-kaori-tab-inactive-classes' in shared_tabs,
        'Shared Content Tabs must own active/inactive visual class contracts.',
        errors,
    )
    require(
        'ANALYTICS_TAB_ACTIVE_CLASSES' not in runtime,
        'Analytics JS must not duplicate shared Content Tab visual classes.',
        errors,
    )
    require(
        'stabilizeAlertsAfterSwap' not in runtime and 'data-alerts-tabset' not in runtime,
        'Analytics runtime must not retain the retired Alerts Alpine-tab rehydration bridge.',
        errors,
    )
    require(
        'kaoriAnalyticsTabs' not in runtime,
        'Analytics tab runtime must not retain the retired Alpine tab factory.',
        errors,
    )
    for forbidden in (
        'const alpineState = tabset._x_dataStack',
        'const alpineTab = tabset._x_dataStack',
    ):
        require(
            forbidden not in runtime,
            f'Analytics tab runtime must not bridge native tabs into Alpine state: {forbidden}',
            errors,
        )

    combined_templates = '\n'.join(path.read_text(encoding='utf-8') for path in ANALYTICS_TEMPLATES.rglob('*.html'))
    require(
        'x-show="activeTab' not in combined_templates,
        'Analytics templates must not duplicate native tab visibility through Alpine x-show.',
        errors,
    )
    require(
        'x-bind:hidden="activeTab' not in combined_templates,
        'Analytics templates must not duplicate native tab visibility through Alpine x-bind:hidden.',
        errors,
    )

    for source_name, source in (
        ('analysis workspace', workspace),
        ('overview', overview),
        ('top consumers', top_consumers),
    ):
        require(
            'components/content_tabs.html' in source,
            f'{source_name} must consume shared KAORI Content Tabs directly.',
            errors,
        )
        require(
            'content_tabs.render_buttons' in source,
            f'{source_name} must use shared Content Tabs buttons.',
            errors,
        )

    for retired in (
        'app/templates/analytics/components/_content_tabs.html',
        'app/templates/analytics/components/_snapshot_panel.html',
        'app/templates/kubernetes/analytics/materialization/_freshness.html',
    ):
        require(
            not (ROOT / retired).exists(),
            f'Retired Analytics compatibility/dead template must be removed: {retired}',
            errors,
        )

    for token in (
        "('utilization', 'Usage'",
        "('workloads', 'Workload'",
        "('action-summary', 'Actions'",
        "('recommendations', 'Guidance'",
        'show_badges=false',
        'nowrap=true',
    ):
        require(token in overview, f'Analytics Overview compact tab contract missing: {token}', errors)
    require(
        "'min-w-max flex-nowrap' if nowrap else 'flex-wrap'" in shared_tabs,
        'Shared Content Tabs must support no-wrap mode for dense Overview navigation.',
        errors,
    )
    require(
        "'overflow-x-auto ' if nowrap else ''" in shared_tabs,
        'No-wrap Content Tabs must retain horizontal overflow fallback on narrow viewports.',
        errors,
    )

    # Final Lock v2: one precise Analytics record-detail vocabulary and one hero ownership model.
    require(
        'View More' not in combined_templates,
        'Analytics record actions must use the precise View Details label instead of ambiguous View More copy.',
        errors,
    )
    for token in (
        'x-teleport="body"',
        "size == 'wide'",
        'max-w-5xl',
        'max-w-4xl',
        '@keydown.escape.window="detailOpen = false"',
    ):
        require(token in record_detail_modal, f'Analytics record-detail modal contract missing: {token}', errors)

    require(
        '{% include "kubernetes/analytics/forecast/partials/_hero.html" %}' in forecast_index,
        'Forecast page must consume the canonical Forecast hero partial.',
        errors,
    )
    require(
        'page_hero.shell_classes()' not in forecast_index,
        'Forecast page must not duplicate hero geometry inline.',
        errors,
    )
    for token in (
        'page_hero.shell_classes()',
        "page_hero.intro('sparkles', 'Kubernetes Analytics', 'line-chart')",
        "'All Namespaces'",
        "url_for('integrations.kubernetes')",
    ):
        require(token in forecast_hero, f'Forecast hero partial missing canonical token: {token}', errors)

    for token in (
        'card.value|default("N/A", true)',
        "identity.entity_label|default('No Evidence', true)",
        "identity.primary|default('No Evidence', true)",
    ):
        require(
            token in top_consumer_summary,
            f'Top Consumer summary must preserve explicit missing-evidence semantics: {token}',
            errors,
        )

    top_level_pages = (
        'app/templates/kubernetes/analytics/overview/index.html',
        'app/templates/kubernetes/analytics/utilization/index.html',
        'app/templates/kubernetes/analytics/capacity/index.html',
        'app/templates/kubernetes/analytics/storage/index.html',
        'app/templates/kubernetes/analytics/workload/index.html',
        'app/templates/kubernetes/analytics/forecast/index.html',
        'app/templates/kubernetes/analytics/top_consumers/index.html',
        'app/templates/kubernetes/analytics/alerts/index.html',
    )
    for relative in top_level_pages:
        source = read(relative)
        require(
            'kaori-analytics-page' in source,
            f'Analytics top-level page must use canonical page spacing: {relative}',
            errors,
        )
        require(
            'dependency_blocker' in source,
            f'Analytics top-level page must preserve selected-cluster dependency guardrail: {relative}',
            errors,
        )

    kubernetes_route_files = tuple(path for path in ROUTE_FILES if 'object_storage' not in str(path))
    kubernetes_permission_guards = sum(
        read(str(path.relative_to(ROOT))).count("@permission_required('analytics.view')")
        for path in kubernetes_route_files
    )
    object_storage_permission_guards = read('app/storage/object_storage/analytics/routes.py').count(
        "@permission_required('object_storage_analytics.view')"
    )
    require(
        kubernetes_permission_guards >= 19,
        'Expected every Kubernetes Analytics full/fragment route to retain analytics.view authorization.',
        errors,
    )
    require(
        object_storage_permission_guards == 10,
        'Expected every Object Storage Analytics full/fragment route to retain object_storage_analytics.view authorization.',
        errors,
    )
    route_source = '\n'.join(read(str(path.relative_to(ROOT))) for path in ROUTE_FILES)
    for forbidden in ('MetricsConsumer(', 'MetricsService(', '.query_range(', '.custom_query('):
        require(
            forbidden not in route_source,
            f'Analytics route layer must not execute provider query directly: {forbidden}',
            errors,
        )

    for relative in RELEASE_EVIDENCE:
        require((ROOT / relative).exists(), f'Analytics release evidence missing: {relative}', errors)
    require(
        'python scripts/verify_analytics_final_lock.py' in quality_gate,
        'quality_gate.sh must execute Analytics final-lock verifier.',
        errors,
    )
    require(
        "-m 'not debug and not e2e'" in quality_gate,
        'quality_gate.sh must retain canonical functional release evidence.',
        errors,
    )
    for relative in RELEASE_EVIDENCE:
        if relative == 'tests/kubernetes/analytics/test_kubernetes_analytics_page_flows.py':
            continue
        require(
            Path(relative).name in coverage,
            f'Analytics release evidence must be registered in feature coverage: {relative}',
            errors,
        )

    require(
        'native `app/static/js/analytics/controls.js` tab controller' in analytics_readme,
        'Analytics README must document single native tab ownership.',
        errors,
    )
    identity = read('app/kubernetes/analytics/materialization/identity.py')
    materialization_service = read('app/kubernetes/analytics/materialization/service.py')
    require(
        'def normalize_parameters' in identity and 'def parameter_fingerprint' in identity,
        'Analytics snapshot identity must be owned by the dependency-light materialization identity module.',
        errors,
    )
    require(
        'def normalize_parameters' not in materialization_service,
        'Materialization service must not duplicate snapshot identity helpers.',
        errors,
    )
    serialization = read('app/kubernetes/analytics/materialization/serialization.py')
    forecast_presentation = read('app/kubernetes/analytics/forecast/presentation.py')
    require(
        'load_cluster_reference' not in serialization,
        'Analytics snapshot decode must not use a database-backed compatibility fallback.',
        errors,
    )
    require(
        '_FORECAST_LEGACY_KEYS' not in forecast_presentation,
        'Forecast reprojection must build only the canonical payload without legacy-key cleanup.',
        errors,
    )
    require(
        'snapshot.last_error_detail' in workspace,
        'Analytics workspace must render parsed refresh error detail.',
        errors,
    )
    require(
        'snapshot.last_error_remediation' in workspace,
        'Analytics workspace must render actionable refresh remediation when available.',
        errors,
    )
    require(
        '{{ snapshot.last_error }}' not in workspace,
        'Analytics workspace must not render the raw stored refresh error directly.',
        errors,
    )
    require(
        'Tab Style 4 — Content Tabs' in tab_registry,
        'Tab Style Registry must register Content Tabs as an approved KAORI style.',
        errors,
    )
    require(
        'Usage · Capacity · Workload · Storage · Consumers · Forecast · Alerts · Actions · Guidance'
        in content_tabs_standard,
        'Content Tabs standard must document the compact Analytics Overview vocabulary.',
        errors,
    )
    require(
        '06 — Kubernetes Analytics' in tracker,
        'Final recheck tracker must include Kubernetes Analytics.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    template_count = sum(1 for _ in ANALYTICS_TEMPLATES.rglob('*.html'))
    print(f'PASS — KAORI Kubernetes Analytics Final Lock v2 · {template_count} templates')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
