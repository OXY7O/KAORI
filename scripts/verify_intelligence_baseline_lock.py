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
    automation_routes = read('app/automation_control/routes.py')
    automation_presentation = read('app/automation_control/presentation.py')
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
        "@intelligence_bp.route('/alert-intelligence')",
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

    for required in (
        "@automation_control_bp.route('/automation-control')",
        "@permission_required('intelligence.view')",
        "current_app.config.get('AUTOMATION_CONTROL_MUTATIONS_ENABLED', False)",
        "title='Automation Control Reserved Plan'",
        "message='KAORI did not apply the requested mutation.'",
    ):
        require(required in automation_routes, f'Automation Control baseline boundary missing: {required}', errors)

    mutation_gate = _function_body(automation_routes, '_handle_mutation', '_actor_user_id')
    gate_position = mutation_gate.index("current_app.config.get('AUTOMATION_CONTROL_MUTATIONS_ENABLED', False)")
    operation_position = mutation_gate.index('operation()')
    require(gate_position < operation_position, 'Automation mutation callback can run before fail-closed gate', errors)
    require('detail=str(exc)' not in automation_routes, 'Automation Control must not disclose exception text', errors)
    require(
        "'mutations_enabled': bool(current_app.config.get('AUTOMATION_CONTROL_MUTATIONS_ENABLED', False))"
        in automation_presentation,
        'Automation Control presentation must expose default-safe mutation state',
        errors,
    )
    require(
        "'posture': {'label': 'Reserved Plan', 'tone': 'unknown'}" in automation_presentation,
        'Automation Control pre-feature-completion posture must remain Reserved Plan',
        errors,
    )
    require(
        'AUTOMATION_CONTROL_MUTATIONS_ENABLED' not in default_config,
        'Automation Control environment enablement must remain deferred during baseline lock',
        errors,
    )

    alert_payload_start = intelligence_service.index('def get_alert_intelligence_payload(')
    alert_payload = intelligence_service[alert_payload_start:]
    for required in (
        "'title': 'Server Signal Enrichment'",
        "'status': 'Reserved Plan'",
        "'title': 'HCI Signal Enrichment'",
        "'title': 'Govern Handoff'",
        "'output': 'Reserved decision candidate'",
        "'Automated mutation while control gates remain disabled'",
    ):
        require(required in alert_payload, f'Alert Intelligence Reserved Plan boundary missing: {required}', errors)

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
        require(
            'intelligence/components/_workspace.html' in page,
            f'{label} must use shared Intelligence workspace',
            errors,
        )

    require('resource_detail_modal.drawer_host(' in recommendations_page, 'Recommendations drawer host missing', errors)
    require(
        'resource_detail_modal.detail_button' in recommendation_records,
        'Recommendations shared detail button missing',
        errors,
    )
    require('data-detail-row' in catalog_records, 'Rule Catalog adjacent detail-row ownership missing', errors)
    require('Read-Only Governance' in automation_page, 'Automation Control must communicate read-only posture', errors)

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
