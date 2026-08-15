#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LOCK_DOCS = (
    'docs/design/KAORI_INTELLIGENCE_BASELINE_LOCK_V1.md',
    'docs/design/audits/KAORI_INTELLIGENCE_BASELINE_LOCK_AUDIT_2026_08_11.md',
)

ARBITRARY_TEXT = re.compile(r'\btext-\[[^\]]+\]')
ARBITRARY_TRACKING = re.compile(r'\btracking-\[[^\]]+\]')
RAW_HEX = re.compile(r'(?<![\w-])#[0-9a-fA-F]{3,8}\b')
INLINE_HANDLER = re.compile(r'\bon(?:click|change|input|submit|load|error|keyup|keydown)\s*=', re.I)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _function_body(source: str, function_name: str, next_function_name: str) -> str:
    start = source.index(f'def {function_name}(')
    end = source.index(f'def {next_function_name}(', start)
    return source[start:end]


def main() -> int:
    errors: list[str] = []

    intelligence_routes = read('app/intelligence/routes.py')
    intelligence_service = read('app/intelligence/service.py')
    intelligence_catalog = read('app/intelligence/catalog.py')
    rule_presentation = read('app/intelligence/rule_presentation.py')
    recommendation_engine = read('app/intelligence/recommendation_engine.py')
    object_storage_recommendations = read('app/intelligence/object_storage_recommendations.py')
    alert_intelligence = read('app/alert_intelligence/service.py')
    alert_routes = read('app/alert_intelligence/routes.py')
    alert_workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    alert_alerts = read('app/templates/intelligence/partials/_alert_intelligence_alerts.html')
    alert_page_partial = read('app/templates/intelligence/partials/_alert_intelligence_page.html')
    alert_summary = read('app/templates/intelligence/partials/_alert_intelligence_summary.html')
    alert_correlation = read('app/templates/intelligence/partials/_alert_intelligence_correlation.html')
    alert_delivery = read('app/templates/intelligence/partials/_alert_intelligence_delivery.html')
    alert_evidence = read('app/templates/intelligence/partials/_alert_intelligence_evidence.html')
    automation_routes = read('app/automation_control/routes.py')
    automation_presentation = read('app/automation_control/presentation.py')
    automation_overview = read('app/automation_control/overview.py')
    readme = read('app/intelligence/README.md')
    standard = read('docs/design/components/INTELLIGENCE_WORKSPACE_STANDARD.md')
    default_config = read('app/config/default.py')
    quality_gate = read('scripts/quality_gate.sh')

    templates = sorted((ROOT / 'app/templates/intelligence').rglob('*.html'))
    require(bool(templates), 'Intelligence templates are missing', errors)
    for path in templates:
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding='utf-8')
        require(not ARBITRARY_TEXT.search(source), f'{relative}: arbitrary text size is forbidden', errors)
        require(not ARBITRARY_TRACKING.search(source), f'{relative}: arbitrary tracking is forbidden', errors)
        require(not RAW_HEX.search(source), f'{relative}: raw hex color is forbidden', errors)
        require('font-extrabold' not in source, f'{relative}: font-extrabold is forbidden', errors)
        require('<script' not in source, f'{relative}: inline script is forbidden', errors)
        require(not INLINE_HANDLER.search(source), f'{relative}: inline DOM handler is forbidden', errors)

    for relative in LOCK_DOCS:
        require((ROOT / relative).exists(), f'missing Intelligence baseline-lock artifact: {relative}', errors)

    for route_signature in (
        "@intelligence_bp.route('/')",
        "@intelligence_bp.route('/recommendations')",
        "@intelligence_bp.get('/recommendations/<path:recommendation_key>/details')",
        "@intelligence_bp.route('/catalog')",
        "@intelligence_bp.get('/catalog/<path:rule_key>/details')",
    ):
        position = intelligence_routes.index(route_signature)
        permission_position = intelligence_routes.index("@permission_required('intelligence.view')", position)
        function_position = intelligence_routes.index('def ', position)
        require(
            position < permission_position < function_position,
            f'Intelligence view permission boundary missing after {route_signature}',
            errors,
        )

    require(
        '@intelligence_bp.post' not in intelligence_routes,
        'Intelligence read domain must not own mutation routes',
        errors,
    )

    for route_signature in (
        "@alert_intelligence_bp.get('')",
        "@alert_intelligence_bp.get('/records')",
    ):
        position = alert_routes.index(route_signature)
        permission_position = alert_routes.index("@permission_required('intelligence.view')", position)
        function_position = alert_routes.index('def ', position)
        require(
            position < permission_position < function_position,
            f'Alert Intelligence view permission boundary missing after {route_signature}',
            errors,
        )
    require('@alert_intelligence_bp.post' not in alert_routes, 'Alert Intelligence read capability must not own mutation routes', errors)

    for required in (
        "@automation_control_bp.route('/automation-control')",
        "@permission_required('intelligence.view')",
        "def _handle_governance_mutation(",
        "def _handle_execution_action(",
        "title='Infrastructure Execution Disabled'",
    ):
        require(required in automation_routes, f'Automation Control baseline boundary missing: {required}', errors)

    governance_gate = _function_body(automation_routes, '_handle_governance_mutation', '_handle_execution_action')
    execution_gate = _function_body(automation_routes, '_handle_execution_action', '_handle_control_operation')
    require('execution_enabled()' not in governance_gate, 'Governance configuration must remain available while execution is disabled', errors)
    require('execution_enabled()' in execution_gate, 'Infrastructure execution route must enforce the fail-closed execution gate', errors)
    require('detail=str(exc)' not in automation_routes, 'Automation Control must not disclose exception text', errors)
    require('Governance Workflow Enabled' in read('app/templates/intelligence/partials/automation_control/_decisions.html'), 'Decision Review must expose active governance workflow semantics', errors)
    require(
        "infrastructure_execution_enabled = execution_enabled()" in automation_presentation,
        'Automation Control presentation must expose default-safe execution state',
        errors,
    )
    require(
        "'posture': overview_state['posture']" in automation_presentation,
        'Automation Control posture must be derived from current automation state',
        errors,
    )
    require(
        "AUTOMATION_EXECUTION_ENABLED = _env_bool('AUTOMATION_EXECUTION_ENABLED', False)" in default_config,
        'Automation Control execution must remain explicitly default-deny',
        errors,
    )
    require(
        'AUTOMATION_CONTROL_MUTATIONS_ENABLED' not in automation_routes + automation_presentation + default_config,
        'Legacy all-mutations gate must not return',
        errors,
    )
    require('Governance Only' in automation_overview, 'Automation Control must communicate factual governance-only posture while execution is disabled', errors)
    require('DOMAIN_DEFINITIONS' not in automation_presentation, 'Legacy Automation Control Foundation Map must not return', errors)

    intelligence_overview = read('app/intelligence/overview.py')
    overview_page = read('app/templates/intelligence/overview.html')
    require(
        "render_template('intelligence/overview.html', payload=payload)" in intelligence_routes,
        'Intelligence root must render the dedicated Overview workspace',
        errors,
    )
    require(
        "redirect(url_for('intelligence.recommendations'))" not in intelligence_routes,
        'Intelligence root must not redirect past the Overview workspace',
        errors,
    )
    for forbidden in ('load_alerts_by_source', 'load_alert_stream', 'PrometheusConsumer', 'MinioClient'):
        require(
            forbidden not in intelligence_overview,
            f'Intelligence Overview must stay provider-free: {forbidden}',
            errors,
        )
    for required in ('Recommendations', 'Alert Intelligence', 'Rule Catalog', 'Automation Control'):
        require(required in intelligence_overview, f'Intelligence Overview capability missing: {required}', errors)
    require('payload.capabilities' in overview_page, 'Intelligence Overview must render owned capability rows', errors)

    require(
        'def get_alert_intelligence_payload(' not in intelligence_service,
        'Alert Intelligence payload ownership must not return to the generic Intelligence service',
        errors,
    )
    for required in (
        'load_alerts_by_source',
        'load_alert_stream',
        'get_active_recommendation_findings',
        'notification_channel_summary',
        'recent_delivery_summary',
        "'kubernetes'",
        "'object_storage'",
        "'auto'",
        "'alertmanager'",
        "'prometheus'",
    ):
        require(required in alert_intelligence, f'Alert Intelligence multi-domain contract missing: {required}', errors)
    alert_surface = '\n'.join(
        (alert_workspace, alert_alerts, alert_summary, alert_correlation, alert_delivery, alert_evidence)
    )
    for required in (
        'Alert Intelligence Summary',
        'Alert Intelligence Workspace',
        'Alert Records',
        'Correlation & Guidance',
        'Notification Delivery',
        'Evidence & Ownership Boundaries',
        'Alertmanager',
        'Prometheus ALERTS',
    ):
        require(required in alert_surface, f'Alert Intelligence workspace contract missing: {required}', errors)
    require(
        'This is contextual correlation, not a claim that every finding was caused by every alert.' in alert_correlation,
        'Alert Intelligence must keep contextual correlation distinct from causal attribution',
        errors,
    )
    require('components/content_tabs.html' in alert_workspace, 'Alert Intelligence must use the shared KAORI Content Tabs component', errors)
    require('content_tabs.render_links(' in alert_workspace, 'Alert Intelligence section state must use server-owned shared Content Tabs links', errors)
    require('intelligence_ui.link_tabs(' not in alert_workspace, 'Alert Intelligence must not keep a page-local underline tab treatment', errors)
    require('nowrap=true' in alert_workspace, 'Alert Intelligence Content Tabs must keep concise long-form section labels on one row with overflow fallback', errors)
    require("hx_sync='#alert-intelligence-page-content:replace'" in alert_workspace, 'Alert Intelligence tab navigation must share the page HTMX synchronization boundary', errors)
    require('Operational Context' in alert_workspace and 'Operational Scope' not in alert_workspace, 'Alert Intelligence must distinguish global operational context from record filters', errors)
    require(alert_workspace.index('content_tabs.render_links(') < alert_workspace.index('Operational Context'), 'Alert Intelligence tabs must precede the shared operational context controls', errors)
    require('data-alert-intelligence-active-section' in alert_workspace, 'Alert Intelligence active section must remain inside the workspace surface', errors)
    require('>Apply<' not in alert_alerts and 'Apply\n' not in alert_alerts, 'Alert record filters must not require an Apply button', errors)
    require('hx-trigger="input changed delay:350ms' in alert_alerts, 'Alert record filters must auto-refresh on search and select changes', errors)
    require('Alert Source Context' in alert_alerts, 'Alert Records tab must retain source context', errors)
    require('Active Recommendations' in alert_correlation and 'Catalog Rules' in alert_correlation, 'Correlation tab context is incomplete', errors)
    require('Delivery Status' in alert_delivery and 'Recent Deliveries' in alert_delivery, 'Notification Delivery tab context is incomplete', errors)
    require('Detection' in alert_evidence and 'Execution' in alert_evidence, 'Evidence tab ownership context is incomplete', errors)
    require('Reset Filters' in alert_alerts, 'Alert Records must retain the standard Reset Filters action', errors)
    require('source=payload.source' in alert_alerts, 'Reset Filters must preserve the shared alert-source context', errors)
    require("_VALID_TABS = {'alerts', 'correlation', 'delivery', 'evidence'}" in alert_intelligence, 'Alert Intelligence tab contract is missing', errors)
    require("tab = _choice(args.get('tab'), _VALID_TABS, 'alerts')" in alert_intelligence, 'Alert Intelligence must normalize tab state server-side', errors)

    recommendations_page = read('app/templates/intelligence/recommendations.html')
    catalog_page = read('app/templates/intelligence/rule_catalog.html')
    alert_page = read('app/templates/intelligence/alert_intelligence.html')
    automation_page = read('app/templates/intelligence/automation_control.html')
    recommendation_records = read('app/templates/intelligence/partials/_recommendation_records.html')
    recommendation_workspace = read('app/templates/intelligence/partials/_recommendations_workspace.html')
    recommendation_filters = read('app/templates/intelligence/partials/_filters.html')
    recommendation_results = read('app/templates/intelligence/partials/_recommendations_results.html')
    recommendation_info = read('app/templates/intelligence/partials/_recommendation_workspace_info.html')
    catalog_records = read('app/templates/intelligence/partials/_catalog_records.html')

    for page, label in (
        (overview_page, 'Intelligence Overview'),
        (recommendations_page, 'Recommendations'),
        (catalog_page, 'Rule Catalog'),
        (alert_page, 'Alert Intelligence'),
        (automation_page, 'Automation Control'),
    ):
        hero_owned = 'components/page_hero.html' in page
        if label == 'Alert Intelligence':
            hero_owned = hero_owned or 'components/page_hero.html' in alert_page_partial
        require(hero_owned, f'{label} must use shared Hero ownership', errors)
        shared_workspace_owned = 'intelligence/components/_workspace.html' in page
        if label == 'Alert Intelligence':
            shared_workspace_owned = shared_workspace_owned or 'intelligence/components/_workspace.html' in alert_surface
        require(
            shared_workspace_owned,
            f'{label} must use shared Intelligence workspace',
            errors,
        )

    for required in (
        "{'value': 'object_storage', 'label': 'Object Storage'}",
        "{'value': 'object_storage_bucket', 'label': 'Object Storage Bucket'}",
        "{'value': 'object_storage_inventory', 'label': 'Object Storage Inventory'}",
    ):
        require(required in rule_presentation, f'Object Storage recommendation filter boundary missing: {required}', errors)
    require(
        'build_object_storage_recommendation_findings(rules)' in intelligence_service,
        'Object Storage recommendation evaluator boundary missing',
        errors,
    )
    require(
        "domain='kubernetes'" in recommendation_engine and 'asset_key=selected_cluster_id' in recommendation_engine,
        'Kubernetes Dashboard recommendation scope must remain explicitly Kubernetes-only',
        errors,
    )
    require(
        "provider_key != 'minio'" in object_storage_recommendations,
        'Object Storage recommendation evaluator must stay provider-qualified for current MinIO support',
        errors,
    )
    require(
        'payload.scope_label' in recommendations_page,
        'Recommendations Hero must use multi-domain scope instead of a hard-coded Kubernetes label',
        errors,
    )

    for required in (
        "'rule_key': 'object_storage.metric.capacity_pressure'",
        "'rule_key': 'object_storage.metric.capacity_critical'",
        "'rule_key': 'object_storage.metric.request_error_pressure'",
        "'rule_key': 'object_storage.metric.request_error_critical'",
        "'rule_key': 'object_storage.metric.requests_waiting'",
        "'rule_key': 'object_storage.metric.offline_nodes'",
        "'provider_keys': ['minio']",
        "'evidence_boundary':",
    ):
        require(required in intelligence_catalog, f'Object Storage Rule Catalog boundary missing: {required}', errors)
    require('prometheus_relationship' not in intelligence_catalog, 'Rule Catalog schema must not remain Prometheus-owned', errors)
    require(
        "{'value': 'minio', 'label': 'MinIO'}" in rule_presentation
        and "selected_provider not in provider_keys(rule)" in rule_presentation,
        'Rule Catalog provider-coverage filter is missing',
        errors,
    )
    require(
        'payload.summary.domains' in catalog_page and 'payload.summary.minio' in catalog_page,
        'Rule Catalog Hero must use dynamic domain and MinIO coverage metadata',
        errors,
    )
    require('3 Asset Domains' not in catalog_page, 'Rule Catalog Hero must not hard-code stale domain count', errors)

    for required in (
        '{% set filter_compact_two_rows = true %}',
    ):
        require(required in recommendation_workspace, 'Recommendations compact two-row filter mode missing', errors)
    require(
        "'lg:grid-cols-12' if filter_compact_two_rows" in recommendation_filters,
        'Recommendations compact filter grid contract missing',
        errors,
    )
    require(
        recommendations_page.index('_recommendation_workspace_info.html')
        < recommendations_page.index("'Recommendation Workspace'"),
        'Recommendation Summary must be a standalone section above Recommendation Workspace',
        errors,
    )
    require(
        'recommendation_summary_oob|default(false)' in recommendation_results
        and '_recommendation_workspace_info.html' in recommendation_results,
        'Recommendation Summary must stay filter-aware through an HTMX out-of-band refresh',
        errors,
    )
    for required in (
        'Recommendation Summary',
        'Matching Findings',
        'Kubernetes',
        'Object Storage',
        'Committed Evidence',
    ):
        require(required in recommendation_info, f'Recommendation summary block missing: {required}', errors)

    require('resource_detail_modal.drawer_host(' in recommendations_page, 'Recommendations drawer host missing', errors)
    require(
        'resource_detail_modal.detail_button' in recommendation_records,
        'Recommendations shared detail button missing',
        errors,
    )
    require('data-detail-row' in catalog_records, 'Rule Catalog adjacent detail-row ownership missing', errors)
    require('Governance Only' in automation_page, 'Automation Control must communicate governance-only posture while execution is disabled', errors)

    for required in (
        'baseline-locked',
        'not declared feature-complete',
        '**Reserved Plan**',
        '`AUTOMATION_EXECUTION_ENABLED=false`',
    ):
        require(required in readme, f'Intelligence README baseline-lock contract missing: {required}', errors)
    require(
        '## Baseline lock semantics' in standard,
        'Intelligence workspace standard lacks baseline-lock semantics',
        errors,
    )
    require(
        'verify_intelligence_baseline_lock.py' in quality_gate,
        'Intelligence Baseline Lock verifier is not release-gated',
        errors,
    )

    if errors:
        print('FAIL — KAORI Intelligence Baseline Lock v1')
        for error in errors:
            print(f'- {error}')
        return 1

    print(f'PASS — KAORI Intelligence Baseline Lock v1 · {len(templates)} templates')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
