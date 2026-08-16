#!/usr/bin/env python3
"""Verify the final Kubernetes Governance release boundary."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_ROUTES = ROOT / 'app/governance/routes.py'
TLS_ROUTES = ROOT / 'app/governance/tls_certificates/routes.py'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def called_name(decorator: ast.expr) -> str | None:
    called = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(called, ast.Name):
        return called.id
    if isinstance(called, ast.Attribute):
        return called.attr
    return None


def permission(function: ast.FunctionDef) -> str | None:
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call) or called_name(decorator) != 'permission_required':
            continue
        if decorator.args and isinstance(decorator.args[0], ast.Constant):
            return str(decorator.args[0].value)
    return None


def main() -> int:
    errors: list[str] = []
    governance_source = GOVERNANCE_ROUTES.read_text(encoding='utf-8')
    tls_source = TLS_ROUTES.read_text(encoding='utf-8')
    tls_tree = ast.parse(tls_source, filename=str(TLS_ROUTES))
    tls_functions = {node.name: node for node in tls_tree.body if isinstance(node, ast.FunctionDef)}

    require(
        '@governance_bp.before_request' not in governance_source,
        'Governance must not short-circuit AuthZ in before_request.',
        errors,
    )
    require(
        'block_clusterless_governance_actions' not in governance_source,
        'Retired Governance Blueprint blocker must remain removed.',
        errors,
    )

    for name, expected_permission in (
        ('tls_certificates_index', 'tls_certificates.view'),
        ('tls_certificates_detail', 'tls_certificates.view'),
        ('tls_certificates_sync', 'tls_certificates.sync'),
        ('tls_certificates_sync_status', 'tls_certificates.sync'),
    ):
        function = tls_functions.get(name)
        require(function is not None, f'TLS Governance route {name} is missing.', errors)
        if function is not None:
            require(
                permission(function) == expected_permission,
                f'{name} must require {expected_permission}.',
                errors,
            )

    for helper in ('_clusterless_read_response', '_clusterless_detail_response', '_clusterless_sync_response'):
        require(
            f'def {helper}(' in tls_source,
            f'TLS Governance must keep authorized readiness helper {helper}.',
            errors,
        )

    require(
        'get_visible_tls_sync_job(public_id=public_id, user_id=int(current_user.id))' in tls_source,
        'TLS sync status must remain requester/subscriber scoped.',
        errors,
    )

    collector = read('app/governance/tls_certificates/collector.py')
    mutation = read('app/governance/tls_certificates/mutation.py')
    require(
        '(secret.data or {}).get(TLS_CRT_KEY)' in collector,
        'TLS collector must read certificate data only.',
        errors,
    )
    require(
        '(secret.data or {}).get(TLS_KEY_KEY)' not in collector,
        'TLS collector must never read private-key data.',
        errors,
    )
    require(
        'scrub_secret_payload(live_secret)' in mutation,
        'TLS mutation must scrub live Secret payloads.',
        errors,
    )
    require(
        'scrub_mapping_values(encoded_data)' in mutation,
        'TLS mutation must scrub encoded upload values.',
        errors,
    )

    job_presentation = read('app/governance/tls_certificates/job_presentation.py')
    require(
        'def get_active_tls_sync_job(' not in job_presentation,
        'Orphan TLS active-job helper must remain removed.',
        errors,
    )

    overview = read('app/templates/governance/overview/index.html')
    hero = read('app/templates/governance/tls_certificates/partials/_hero.html')
    table = read('app/templates/governance/tls_certificates/partials/_table.html')
    page = read('app/templates/governance/tls_certificates/index.html')
    require(
        'page_hero.context_header(' in overview,
        'Governance Overview Hero must use the Context Icon Box.',
        errors,
    )
    require(
        'components/cluster/_hero_blocked_context.html' in overview and 'Governance Readiness' in overview,
        'Governance Overview must use the canonical Kubernetes setup-blocked Hero context.',
        errors,
    )
    require(
        'Governance Controls' in overview and "meta_label('server-cog', 'Kubernetes Operations')" not in overview,
        'Governance Overview Hero metadata must remain governance-specific.',
        errors,
    )
    require(
        'page_hero.context_card(' in hero,
        'TLS Governance Hero must use the canonical status-oriented context card.',
        errors,
    )
    require(
        'components/cluster/_hero_blocked_context.html' in hero and 'Governance Readiness' in hero,
        'TLS Governance Hero must use the canonical Kubernetes setup-blocked Hero context.',
        errors,
    )
    page_content = read('app/templates/governance/tls_certificates/partials/_page_content.html')
    require(
        page_content.find('{% if cluster_onboarding.is_blocked %}')
        < page_content.find('{% elif not payload.schema_readiness.ready %}')
        < page_content.find('partials/_page_workspace.html'),
        'TLS Governance must evaluate cluster setup before schema readiness and workspace rendering.',
        errors,
    )
    for token in (
        'components/table.html',
        'components/table_label.html',
        'components/pagination.html',
        'components/resource_detail_modal.html',
    ):
        require(token in table, f'TLS registry must keep shared component ownership: {token}', errors)
    require(
        'detail_button(' in table and 'resource_detail_modal.host(' in page,
        'TLS detail disclosure must remain the Full Workspace Modal.',
        errors,
    )
    detail = read('app/templates/governance/tls_certificates/partials/_detail_content.html')
    summary = read('app/templates/governance/tls_certificates/partials/_summary_cards.html')
    rotate = read('app/templates/kubernetes_operations/secrets/tls_rotate.html')
    require(
        'detail.header_badge_row()' in detail
        and 'data-kaori-tls-detail-layout="evidence-workspace-v2"' in detail
        and 'Certificate Identity &amp; Validity' in detail
        and 'Coverage &amp; Consumer Evidence' in detail
        and 'Collection &amp; Governance' in detail
        and 'detail.detail_card(' not in detail,
        'TLS Certificate Detail must retain the compact evidence-workspace composition and aligned status header.',
        errors,
    )
    require(
        'Certificate Validity & Operations' in summary and 'partials/_sync_panel.html' in summary,
        'TLS posture and inventory operations must remain consolidated in one Governance workspace section.',
        errors,
    )
    require(
        'Replacement Certificate Pair & Validation' in rotate
        and 'Controlled Rotation & Governance Posture' in rotate
        and 'context_rail.html' not in rotate,
        'Single TLS rotation must retain the full-width integrated three-section workspace.',
        errors,
    )
    require(
        'md:grid-cols-3' in rotate
        and 'sm:grid-cols-2 xl:grid-cols-4' in rotate
        and 'lg:grid-cols-[minmax(0,1.45fr)_minmax(18rem,0.55fr)]' in rotate
        and 'xl:grid-cols-[minmax(20rem,0.72fr)_minmax(0,1.28fr)]' not in rotate,
        'Single TLS rotation must retain the compact target identity strip and posture evidence grid.',
        errors,
    )
    constants = read('app/governance/tls_certificates/constants.py')
    for option in ('5', '10', '25', '50'):
        require(option in constants, f'TLS pagination standard must retain {option}.', errors)

    standard = read('docs/design/patterns/KUBERNETES_TLS_CERTIFICATE_GOVERNANCE.md')
    audit = read('docs/design/audits/KUBERNETES_GOVERNANCE_FINAL_RECHECK_2026_08.md')
    for phrase in ('Authorization before readiness', 'Context Icon Box', 'Status Badge Box', 'L0–L7'):
        require(phrase in standard or phrase in audit, f'Governance documentation must record {phrase}.', errors)

    quality_gate = read('scripts/quality_gate.sh')
    core_lock = read('scripts/verify_core_kubernetes_final_lock.py')
    coverage = read('scripts/verify_feature_test_coverage.py')
    require(
        'python scripts/verify_governance_final_lock.py' in quality_gate,
        'quality_gate.sh must run Governance final lock.',
        errors,
    )
    require(
        'verify_governance_final_lock.py' in core_lock,
        'Core Kubernetes lock must own Governance final lock.',
        errors,
    )
    for path in (
        'tests/contracts/governance/test_governance_final_release_contract.py',
        'tests/unit/governance/test_tls_governance_policy.py',
        'tests/governance/test_tls_governance_route_characterization.py',
        'tests/security/governance/test_tls_governance_security.py',
        'tests/rendering/governance/test_tls_governance_rendering.py',
        'tests/integration/governance/test_tls_certificate_read_model.py',
        'tests/e2e/governance/test_tls_governance_smoke.py',
    ):
        require(path in coverage, f'Governance release evidence is not permanent: {path}', errors)

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Kubernetes Governance Final Lock v1 passed: AuthZ-first readiness, TLS evidence minimization, '
        'canonical Hero/table/modal/pagination ownership, user-scoped sync status, dead-surface cleanup, and L0–L7 '
        'release evidence are aligned.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
