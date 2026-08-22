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
    alert_intelligence = read('app/intelligence/alert_intelligence/service.py')
    alert_routes = read('app/intelligence/alert_intelligence/routes.py')
    alert_lifecycle = read('app/intelligence/alert_intelligence/lifecycle.py')
    alert_case_state = read('app/intelligence/alert_intelligence/case_state.py')
    alert_notifications = read('app/intelligence/alert_intelligence/notifications.py')
    alert_routing = read('app/intelligence/alert_intelligence/routing.py')
    alert_templates = read('app/intelligence/alert_intelligence/templates.py')
    alert_workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    alert_active = read('app/templates/intelligence/partials/_alert_ops_active.html')
    alert_history = read('app/templates/intelligence/partials/_alert_ops_history.html')
    alert_page_content = read('app/templates/intelligence/partials/_alert_intelligence_page.html')
    automation_routes = read('app/intelligence/automation_control/routes.py')
    automation_presentation = read('app/intelligence/automation_control/presentation.py')
    automation_overview = read('app/intelligence/automation_control/overview.py')
    automation_enablement = read('app/common/automation_execution.py')
    workflow = read('app/intelligence/workflow.py')
    resolver_tasks = read('app/intelligence/resolver/tasks.py')
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
    for route_signature in (
        "@alert_intelligence_bp.post('/cases/<string:public_id>/acknowledge')",
        "@alert_intelligence_bp.post('/cases/<string:public_id>/assign')",
        "@alert_intelligence_bp.post('/cases/<string:public_id>/mitigating')",
        "@alert_intelligence_bp.post('/cases/<string:public_id>/silence')",
        "@alert_intelligence_bp.post('/cases/<string:public_id>/unsilence')",
        "@alert_intelligence_bp.post('/cases/<string:public_id>/routing/suppress')",
        "@alert_intelligence_bp.post('/cases/<string:public_id>/routing/resume')",
        "@alert_intelligence_bp.post('/cases/<string:public_id>/withdraw')",
        "@alert_intelligence_bp.post('/cases/<string:public_id>/retire-source')",
        "@alert_intelligence_bp.post('/cases/<string:public_id>/close')",
        "@alert_intelligence_bp.post('/cases/<string:public_id>/postmortem')",
    ):
        position = alert_routes.index(route_signature)
        permission_position = alert_routes.index("@permission_required('intelligence.decisions.create')", position)
        function_position = alert_routes.index('def ', position)
        require(
            position < permission_position < function_position,
            f'Alert Operations decision permission boundary missing after {route_signature}',
            errors,
        )
    for route_signature in (
        "@alert_intelligence_bp.post('/routing')",
        "@alert_intelligence_bp.post('/templates')",
    ):
        position = alert_routes.index(route_signature)
        permission_position = alert_routes.index("@permission_required('integrations.manage')", position)
        function_position = alert_routes.index('def ', position)
        require(
            position < permission_position < function_position,
            f'Alert Operations integration-governance permission boundary missing after {route_signature}',
            errors,
        )

    for required in (
        "@automation_control_bp.route('/automation-control')",
        "@permission_required('intelligence.view')",
        "title='Infrastructure Execution Disabled'",
        'execution_enabled()',
    ):
        require(required in automation_routes, f'Automation Control baseline boundary missing: {required}', errors)

    execution_gate = _function_body(automation_routes, '_handle_execution_action', '_handle_control_operation')
    require(
        'execution_enabled()' in execution_gate,
        'Automation infrastructure execution must remain behind the canonical fail-closed enablement gate',
        errors,
    )
    governance_gate = _function_body(automation_routes, '_handle_governance_mutation', '_handle_execution_action')
    require(
        'execution_enabled()' not in governance_gate,
        'Governance mutation must remain available independently from infrastructure execution',
        errors,
    )
    require('detail=str(exc)' not in automation_routes, 'Automation Control must not disclose exception text', errors)
    require(
        "AUTOMATION_EXECUTION_ENABLED = _env_bool('AUTOMATION_EXECUTION_ENABLED', False)" in default_config,
        'Automation execution must remain explicitly fail-closed in default configuration',
        errors,
    )
    require(
        'AUTOMATION_EXECUTION_ENABLED' in automation_enablement,
        'Automation execution enablement contract is missing',
        errors,
    )
    require('assert_execution_enabled()' in workflow, 'Intelligence workflow must enforce execution enablement', errors)
    require('assert_execution_enabled()' in resolver_tasks, 'Resolver tasks must enforce execution enablement', errors)
    require(
        'AUTOMATION_CONTROL_MUTATIONS_ENABLED' not in automation_routes + automation_presentation + default_config,
        'Retired Automation Control mutation compatibility gate must not return',
        errors,
    )
    require(
        'Governance Workflow Enabled' in read('app/templates/intelligence/partials/automation_control/_decisions.html'),
        'Decision Review must expose active governance workflow semantics',
        errors,
    )
    require(
        "'posture': overview_state['posture']" in automation_presentation,
        'Automation Control posture must be derived from current automation state',
        errors,
    )
    require(
        'Governance Only' in automation_overview,
        'Automation Control must communicate factual governance-only posture while mutations are disabled',
        errors,
    )
    require(
        'DOMAIN_DEFINITIONS' not in automation_presentation,
        'Legacy Automation Control Foundation Map must not return',
        errors,
    )

    require(
        'def get_alert_intelligence_payload(' not in intelligence_service,
        'Alert Intelligence payload ownership must not return to the generic Intelligence service',
        errors,
    )
    for required in (
        'notification_channel_summary',
        "AlertCase.source_type == 'recommendation'",
        'routing_policy_rows',
        'built_in_templates',
        "'kubernetes'",
        "'object_storage'",
        "'overview'",
        "'active'",
        "'routing'",
        "'templates'",
        "'silences'",
        "'resolved'",
    ):
        require(required in alert_intelligence, f'Alert Operations multi-domain contract missing: {required}', errors)
    for forbidden in ('load_alerts_by_source', 'load_alert_stream'):
        require(
            forbidden not in alert_intelligence + alert_routes,
            f'Alert Operations web request path must not perform live provider reads: {forbidden}',
            errors,
        )
    for required in (
        'Overview',
        'Active Alerts',
        'Routing & Channels',
        'Templates',
        'Silences',
        'Resolved',
    ):
        require(required in alert_workspace, f'Alert Operations workspace contract missing: {required}', errors)
    for required in ('Clear Filters', 'Workflow', 'alert-operations-filter-form'):
        require(required in alert_active, f'Alert Operations active-alert contract missing: {required}', errors)
    for required in ('Resolved Alerts', 'Resolution Evidence', 'Closure Evidence', 'Postmortem'):
        require(required in alert_history, f'Alert Operations history contract missing: {required}', errors)
    for required in (
        'acknowledge_case',
        'create_delivery_silence',
        'close_case',
        'save_postmortem',
        "case.workflow_state = 'verification_pending'",
    ):
        require(required in alert_lifecycle, f'Alert Operations lifecycle contract missing: {required}', errors)
    for required in (
        'mark_case_source_unknown',
        'restore_case_source_firing',
        'suppress_case_routing',
        'resume_case_routing',
    ):
        require(required in alert_case_state, f'Alert Operations case-state contract missing: {required}', errors)
    for required in (
        "event_state='firing'",
        "event_state='resolved'",
        "case.workflow_state == 'closed'",
        '_successful_firing_channels',
    ):
        require(required in alert_notifications, f'Alert Operations notification lifecycle missing: {required}', errors)
    require(
        'NotificationChannel' in alert_routing and 'credential_payload' not in alert_routing,
        'Alert Operations routing must reference Integration Notification Channels without owning credentials',
        errors,
    )
    for required in ("'telegram'", "'email'", "'microsoft_teams'", "'firing'", "'resolved'"):
        require(required in alert_templates, f'Alert Operations provider-template contract missing: {required}', errors)

    recommendations_page = read('app/templates/intelligence/recommendations.html')
    catalog_page = read('app/templates/intelligence/rule_catalog.html')
    alert_page = read('app/templates/intelligence/alert_intelligence.html')
    automation_page = read('app/templates/intelligence/automation_control.html')
    recommendation_records = read('app/templates/intelligence/partials/_recommendation_records.html')
    catalog_records = read('app/templates/intelligence/partials/_catalog_records.html')

    for page, label in (
        (recommendations_page, 'Recommendations'),
        (catalog_page, 'Rule Catalog'),
        (automation_page, 'Automation Control'),
    ):
        require('components/page_hero.html' in page, f'{label} must use shared Hero ownership', errors)
        require(
            'intelligence/components/_workspace.html' in page,
            f'{label} must use shared Intelligence workspace',
            errors,
        )
    require(
        'intelligence/partials/_alert_intelligence_page.html' in alert_page
        and 'components/page_hero.html' in alert_page_content,
        'Alert Intelligence must use shared Hero ownership through its HTMX page-content partial',
        errors,
    )
    require(
        'intelligence/components/_workspace.html' in alert_workspace,
        'Alert Intelligence must use shared Intelligence workspace',
        errors,
    )

    for required in (
        "{'value': 'object_storage', 'label': 'Object Storage'}",
        "{'value': 'object_storage_bucket', 'label': 'Object Storage Bucket'}",
        "{'value': 'object_storage_inventory', 'label': 'Object Storage Inventory'}",
    ):
        require(
            required in rule_presentation, f'Object Storage recommendation filter boundary missing: {required}', errors
        )
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
        'rule_key: object_storage.metric.capacity_pressure',
        'rule_key: object_storage.metric.capacity_critical',
        'rule_key: object_storage.metric.request_error_pressure',
        'rule_key: object_storage.metric.request_error_critical',
        'rule_key: object_storage.metric.requests_waiting',
        'rule_key: object_storage.metric.offline_nodes',
        'provider_keys:',
        'evidence_boundary:',
    ):
        require(required in intelligence_catalog, f'Object Storage Rule Catalog boundary missing: {required}', errors)
    require(
        'prometheus_relationship' not in intelligence_catalog,
        'Rule Catalog schema must not remain Prometheus-owned',
        errors,
    )
    require(
        "{'value': 'minio', 'label': 'MinIO'}" in rule_presentation
        and 'selected_provider not in provider_keys(rule)' in rule_presentation,
        'Rule Catalog provider-coverage filter is missing',
        errors,
    )
    require(
        'payload.summary.domains' in catalog_page and 'Canonical Definitions' in catalog_page,
        'Rule Catalog Hero must use provider-neutral dynamic domain metadata',
        errors,
    )
    require(
        'payload.summary.minio' not in catalog_page and 'MinIO-Covered Rules' not in catalog_page,
        'Rule Catalog Hero must not expose provider-specific coverage as a global summary',
        errors,
    )
    require('3 Asset Domains' not in catalog_page, 'Rule Catalog Hero must not hard-code stale domain count', errors)

    require('resource_detail_modal.host(' in recommendations_page, 'Recommendations modal host missing', errors)
    require(
        'resource_detail_modal.detail_button' in recommendation_records,
        'Recommendations shared detail button missing',
        errors,
    )
    require('data-detail-row' in catalog_records, 'Rule Catalog adjacent detail-row ownership missing', errors)
    require(
        'Governance Only' in automation_page,
        'Automation Control must communicate governance-only posture while mutations are disabled',
        errors,
    )

    for required in (
        'baseline-locked',
        'not declared feature-complete',
        '**Reserved Plan**',
        'AUTOMATION_EXECUTION_ENABLED=false',
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
