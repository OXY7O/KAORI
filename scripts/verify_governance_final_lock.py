#!/usr/bin/env python3
"""Verify the final Kubernetes Governance release boundary."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_ROUTES = ROOT / 'app/kubernetes/governance/routes.py'
TLS_ROUTES = ROOT / 'app/kubernetes/governance/tls_certificates/routes.py'


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

    for token in (
        "@permission_required('governance.view')",
        "can_view_tls = current_user.has_permission('tls_certificates.view')",
    ):
        require(
            token in governance_source,
            f'Governance Overview route must preserve domain authorization and child-capability visibility: {token}',
            errors,
        )
    for retired_dependency in ('get_tls_certificate_page', 'tls_payload'):
        require(
            retired_dependency not in governance_source,
            f'Governance Overview route must not load full child-capability evidence: {retired_dependency}',
            errors,
        )
    permission_position = governance_source.find("can_view_tls = current_user.has_permission('tls_certificates.view')")
    cluster_gate_position = governance_source.find('if can_view_tls and has_registered_clusters() is True:')
    snapshot_read_position = governance_source.find('tls_snapshot = get_tls_collection_snapshot()')
    require(
        0 <= permission_position < cluster_gate_position < snapshot_read_position,
        'TLS snapshot retrieval must follow child permission and cluster-readiness checks.',
        errors,
    )

    # Internal PKI source-readiness is a real read-only cluster registry,
    # not fabricated control-plane certificate evidence or an executable renewal.
    internal_routes = read('app/kubernetes/governance/internal_certificates/routes.py')
    internal_service = read('app/kubernetes/governance/internal_certificates/service.py')
    internal_page = read('app/templates/kubernetes/governance/internal_certificates/index.html')
    access_defaults = read('app/definitions/catalogs/access/rbac/access.yaml')
    governance_overview = read('app/templates/kubernetes/governance/overview/index.html')
    for guard in (
        "@permission_required('governance.view')",
        "@permission_required('clusters.view')",
        "@permission_required('internal_certificates.view')",
    ):
        require(guard in internal_routes, f'Internal PKI source route missing guard: {guard}', errors)
    require(
        'if registered_clusters is True else None' in internal_routes,
        'Internal PKI must block clusterless/unknown source reads before hitting the registry.',
        errors,
    )
    for item in (
        'db.session.execute(',
        'KubernetesConnection.detected_platform',
        'KubernetesConnection.detected_version',
        "'collection_status': 'Not Collected'",
        "'authority_status': 'Not Verified'",
        "'expiry_status': 'Unknown'",
        '_DEFAULT_PER_PAGE = 5',
    ):
        require(item in internal_service, f'Internal PKI source projection is missing: {item}', errors)
    for forbidden in ('get_integration(', 'get_tls_certificate_page(', 'kubeadm certs renew'):
        require(
            forbidden not in internal_service and forbidden not in internal_routes,
            f'Internal PKI read-only route must not collect or mutate source data: {forbidden}',
            errors,
        )
    for item in (
        'Internal PKI Source Registry',
        "registry_ui.filter_form('governance.internal_certificates'",
        "registry_ui.footer('governance.internal_certificates'",
        'Not Collected',
        'Not Verified',
        'Renewal Deferred',
    ):
        require(item in internal_page, f'Internal PKI workspace is missing: {item}', errors)
    require(
        'Request Renewal' not in internal_page and 'Rotate All' not in internal_page,
        'Internal PKI source readiness must remain non-mutating.',
        errors,
    )
    for item in (
        "'title': 'Internal Certificates'",
        "'status': 'Source Pending'",
        "'available': can_view_internal_certificates",
        'sm:grid-cols-2',
    ):
        require(item in governance_overview, f'Governance needs a truthful second capability: {item}', errors)
    require(
        'internal_certificates.view: [governance.view, clusters.view]' in access_defaults,
        'Internal PKI must use the canonical dependent RBAC permission.',
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

    collector = read('app/kubernetes/governance/tls_certificates/collector.py')
    mutation = read('app/kubernetes/governance/tls_certificates/mutation.py')
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

    job_presentation = read('app/kubernetes/governance/tls_certificates/job_presentation.py')
    require(
        'def get_active_tls_sync_job(' not in job_presentation,
        'Orphan TLS active-job helper must remain removed.',
        errors,
    )

    overview = read('app/templates/kubernetes/governance/overview/index.html')
    hero = read('app/templates/kubernetes/governance/tls_certificates/partials/_hero.html')
    table = read('app/templates/kubernetes/governance/tls_certificates/partials/_table.html')
    page = read('app/templates/kubernetes/governance/tls_certificates/index.html')
    require(
        'page_hero.context_card(' in overview
        and "'Open Cluster Integrations'" in overview
        and "url_for('integrations.kubernetes')" in overview,
        'Governance Overview ready Hero must use the canonical generic context card and Open Cluster Integrations action.',
        errors,
    )
    require(
        'components/cluster/_hero_blocked_context.html' in overview and 'Governance Readiness' in overview,
        'Governance Overview must use the canonical Kubernetes setup-blocked Hero context.',
        errors,
    )
    require(
        'Governance Controls' in overview
        and 'Committed Evidence' in overview
        and 'Governed Handoffs' in overview
        and "meta_label('server-cog', 'Kubernetes Operations')" not in overview,
        'Governance Overview Hero metadata must remain domain-governance specific.',
        errors,
    )

    for token in (
        'Review Kubernetes governance controls, evidence, and ownership.',
        'Governance Capabilities',
        'Open independent governance workspaces with explicit evidence and source-readiness status.',
        'sm:grid-cols-2',
        "'title': 'TLS Certificates'",
        "'action': 'Open TLS Certificates' if can_view_tls else 'View Permission Required'",
        'Governance Operating Model',
        'Provider Authority',
        'Policy & Guardrails',
        'Committed Evidence',
        'Controlled Handoffs',
        'KAORI applies governance policy and authorization guardrails without cloning the provider control plane.',
        'View Permission Required',
        'header_badge=capability_badge',
        "info_tip.render('governance-operating-model-guide'",
        "variant='guide'",
        'header_badge=model_guide',
        'overflow-hidden rounded-xl border border-outline-subtle',
        'workspace_card.render(',
        'compact=true',
        'kubernetes/governance/tls_certificates/partials/_snapshot_context.html',
        '{% if can_view_tls and tls_snapshot is not none %}',
    ):
        require(token in overview, f'Governance Overview composition is missing: {token}', errors)

    for token in (
        'Governance Control Context',
        '[grid-template-columns:repeat(auto-fit',
        'components/snapshot_context_bar.html',
        'get_tls_certificate_page',
        'tls_payload',
        'New governance capabilities join this catalog only after implementation',
    ):
        require(token not in overview, f'Governance Overview contains retired pattern: {token}', errors)

    context_position = overview.index('partials/_snapshot_context.html')
    scope_position = overview.index("section_intro.render('Governance Scope'")
    require(
        context_position < scope_position,
        'Authorized TLS snapshot must follow Hero and precede Governance Scope.',
        errors,
    )
    require(
        "action_href=url_for('governance.tls_certificates')" not in overview
        and "action_label='Open TLS Certificates'" not in overview,
        'Governance Capabilities parent card must not own a TLS-specific action.',
        errors,
    )
    for token in (
        "can_view_tls = current_user.has_permission('tls_certificates.view')",
        'if can_view_tls and has_registered_clusters() is True:',
        'tls_snapshot = get_tls_collection_snapshot()',
    ):
        require(
            token in governance_source,
            f'Governance Overview must guard committed TLS evidence before reading it: {token}',
            errors,
        )

    service = read('app/kubernetes/governance/tls_certificates/service.py')
    for token in (
        'def get_tls_collection_snapshot() -> dict[str, Any]:',
        'check_tls_governance_schema_readiness()',
        'return _collection_snapshot(',
        "summary={'total': total}",
    ):
        require(token in service, f'TLS snapshot reuse must preserve committed read model: {token}', errors)

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
    page_content = read('app/templates/kubernetes/governance/tls_certificates/partials/_page_content.html')
    workspace = read('app/templates/kubernetes/governance/tls_certificates/partials/_page_workspace.html')
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
    detail = read('app/templates/kubernetes/governance/tls_certificates/partials/_detail_content.html')
    summary = read('app/templates/kubernetes/governance/tls_certificates/partials/_summary_cards.html')
    rotate = read('app/templates/kubernetes/operations/secrets/tls_rotate.html')
    require(
        'detail.header_identity_row()' in detail
        and 'detail.header_badge_row()' not in detail
        and 'data-kaori-tls-detail-layout="evidence-workspace-v2"' in detail
        and 'Certificate Identity &amp; Validity' in detail
        and 'Coverage &amp; Consumer Evidence' in detail
        and 'Collection &amp; Governance' in detail
        and 'detail.detail_card(' not in detail,
        'TLS Certificate Detail must retain the compact evidence-workspace composition and aligned status header.',
        errors,
    )
    require(
        'Certificate Validity' in summary
        and 'Certificate Validity & Operations' not in summary
        and 'partials/_sync_panel.html' not in summary
        and workspace.find('partials/_sync_panel.html') < workspace.find("'Certificate Posture'"),
        'TLS posture and inventory operations must retain the canonical Governance workspace hierarchy.',
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
        and 'lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]' in rotate
        and 'xl:grid-cols-[minmax(20rem,0.72fr)_minmax(0,1.28fr)]' not in rotate,
        'Single TLS rotation must retain the compact target identity strip and posture evidence grid.',
        errors,
    )
    constants = read('app/kubernetes/governance/tls_certificates/constants.py')
    for option in ('5', '10', '25', '50'):
        require(option in constants, f'TLS pagination standard must retain {option}.', errors)

    standard = read('docs/design/patterns/KUBERNETES_TLS_CERTIFICATE_GOVERNANCE.md')
    audit = read('docs/design/audits/KUBERNETES_GOVERNANCE_FINAL_RECHECK_2026_08.md')
    for phrase in (
        'Authorization before readiness',
        'Context Icon Box',
        'Status Badge Box',
        'Governance Overview landing contract',
        'L0–L7',
    ):
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
        'tests/contracts/kubernetes/governance/test_governance_final_release_contract.py',
        'tests/unit/kubernetes/governance/test_tls_governance_policy.py',
        'tests/kubernetes/governance/test_tls_governance_route_characterization.py',
        'tests/security/kubernetes/governance/test_tls_governance_security.py',
        'tests/rendering/kubernetes/governance/test_tls_governance_rendering.py',
        'tests/integration/kubernetes/governance/test_tls_certificate_read_model.py',
        'tests/e2e/kubernetes/governance/test_tls_governance_smoke.py',
    ):
        require(path in coverage, f'Governance release evidence is not permanent: {path}', errors)

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Kubernetes Governance Final Lock v1 passed: AuthZ-first readiness, TLS evidence minimization, '
        'domain-first Governance Overview, canonical Hero/table/modal/pagination ownership, user-scoped sync status, '
        'scalable capability catalog, dead-surface cleanup, and L0–L7 release evidence are aligned.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
