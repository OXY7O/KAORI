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
    intelligence_catalog = read('app/definitions/catalogs/intelligence/rules.yaml')
    rule_presentation = read('app/intelligence/rule_presentation.py')
    recommendation_engine = read('app/intelligence/recommendation_engine.py')
    object_storage_recommendations = read('app/intelligence/object_storage_recommendations.py')
    alert_intelligence = read('app/alert_intelligence/service.py')
    alert_routes = read('app/alert_intelligence/routes.py')
    alert_workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
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
        "current_app.config.get('AUTOMATION_CONTROL_MUTATIONS_ENABLED', False)",
        "title='Automation Mutation Disabled'",
        "message='KAORI did not apply the requested control-plane change.'",
    ):
        require(required in automation_routes, f'Automation Control baseline boundary missing: {required}', errors)

    mutation_gate = _function_body(automation_routes, '_handle_mutation', '_handle_control_operation')
    gate_position = mutation_gate.index("current_app.config.get('AUTOMATION_CONTROL_MUTATIONS_ENABLED', False)")
    operation_position = mutation_gate.index('_handle_control_operation(')
    require(gate_position < operation_position, 'Automation execution-control callback can cross the fail-closed gate', errors)
    require('detail=str(exc)' not in automation_routes, 'Automation Control must not disclose exception text', errors)
    governance_gate = _function_body(automation_routes, '_handle_governance_action', '_handle_mutation')
    require('AUTOMATION_CONTROL_MUTATIONS_ENABLED' not in governance_gate, 'Decision governance must remain available while infrastructure mutation is disabled', errors)
    require('Governance Workflow Enabled' in read('app/templates/intelligence/partials/automation_control/_decisions.html'), 'Decision Review must expose active governance workflow semantics', errors)
    require(
        "mutations_enabled = bool(current_app.config.get('AUTOMATION_CONTROL_MUTATIONS_ENABLED', False))"
        in automation_presentation,
        'Automation Control presentation must expose default-safe mutation state',
        errors,
    )
    require(
        "'posture': overview_state['posture']" in automation_presentation,
        'Automation Control posture must be derived from current automation state',
        errors,
    )
    require(
        'AUTOMATION_CONTROL_MUTATIONS_ENABLED' not in default_config,
        'Automation Control environment enablement must remain deferred during baseline lock',
        errors,
    )
    require('Governance Only' in automation_overview, 'Automation Control must communicate factual governance-only posture while mutations are disabled', errors)
    require('DOMAIN_DEFINITIONS' not in automation_presentation, 'Legacy Automation Control Foundation Map must not return', errors)

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
    for required in (
        'Alert Overview',
        'Alert Records',
        'Correlation',
        'Notification Delivery',
        'Evidence',
        'Alertmanager is preferred',
        'Prometheus ALERTS',
    ):
        require(required in alert_workspace, f'Alert Intelligence workspace contract missing: {required}', errors)
    require(
        'This is contextual correlation, not a claim that every finding was caused by every alert.' in alert_workspace,
        'Alert Intelligence must keep contextual correlation distinct from causal attribution',
        errors,
    )

    recommendations_page = read('app/templates/intelligence/recommendations.html')
    catalog_page = read('app/templates/intelligence/rule_catalog.html')
    alert_page = read('app/templates/intelligence/alert_intelligence.html')
    automation_page = read('app/templates/intelligence/automation_control.html')
    recommendation_records = read('app/templates/intelligence/partials/_recommendation_records.html')
    catalog_records = read('app/templates/intelligence/partials/_catalog_records.html')

    for page, label in (
        (recommendations_page, 'Recommendations'),
        (catalog_page, 'Rule Catalog'),
        (alert_page, 'Alert Intelligence'),
        (automation_page, 'Automation Control'),
    ):
        require('components/page_hero.html' in page, f'{label} must use shared Hero ownership', errors)
        shared_workspace_owned = 'intelligence/components/_workspace.html' in page
        if label == 'Alert Intelligence':
            shared_workspace_owned = shared_workspace_owned or 'intelligence/components/_workspace.html' in alert_workspace
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
        "rule_key: object_storage.metric.capacity_pressure",
        "rule_key: object_storage.metric.capacity_critical",
        "rule_key: object_storage.metric.request_error_pressure",
        "rule_key: object_storage.metric.request_error_critical",
        "rule_key: object_storage.metric.requests_waiting",
        "rule_key: object_storage.metric.offline_nodes",
        "provider_keys:",
        "evidence_boundary:",
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

    require('resource_detail_modal.drawer_host(' in recommendations_page, 'Recommendations drawer host missing', errors)
    require(
        'resource_detail_modal.detail_button' in recommendation_records,
        'Recommendations shared detail button missing',
        errors,
    )
    require('data-detail-row' in catalog_records, 'Rule Catalog adjacent detail-row ownership missing', errors)
    require('Governance Only' in automation_page, 'Automation Control must communicate governance-only posture while mutations are disabled', errors)

    for required in (
        'baseline-locked',
        'not declared feature-complete',
        '**Reserved Plan**',
        'intentionally not exposed as an environment-configured release toggle',
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
