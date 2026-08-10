from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    create = read('app/kubernetes_operations/secrets/create_service.py')
    replace = read('app/kubernetes_operations/secrets/replace_service.py')
    delete = read('app/kubernetes_operations/secrets/delete_service.py')
    impact = read('app/kubernetes_operations/secrets/impact.py')
    receipts = read('app/kubernetes_operations/secrets/receipts.py')
    live = read('app/kubernetes_operations/secrets/live_service.py')
    overview = read('app/kubernetes_operations/secrets/service.py')
    crud_routes = read('app/kubernetes_operations/secrets/crud_routes.py')
    reveal_routes = read('app/kubernetes_operations/secrets/reveal_routes.py')
    tls_routes = read('app/kubernetes_operations/secrets/tls_routes.py')
    tls_service = read('app/governance/tls_certificates/service.py')
    tls_updates = read('app/governance/tls_certificates/updates.py')
    tls_mutation = read('app/governance/tls_certificates/mutation.py')
    rbac_defaults = read('app/rbac/defaults.py')
    rbac_service = read('app/rbac/service.py')
    governance_routes = read('app/governance/routes.py')
    tls_governance_routes = read('app/governance/tls_certificates/routes.py')
    tls_collector = read('app/governance/tls_certificates/collector.py')
    permission_migration = read('migrations/versions/20260805_secret_ops_v2.py')
    operation_routes = read('app/kubernetes_operations/routes.py')
    delete_target = read('app/templates/kubernetes_operations/secrets/_delete_target.html')
    delete_actions = read('app/templates/kubernetes_operations/secrets/_delete_actions.html')
    landing = read('app/templates/kubernetes_operations/secrets/index.html')
    reveal_value = read('app/templates/kubernetes_operations/secrets/_reveal_value.html')
    delete_js = read('app/static/js/secret_delete.js')
    standard = read('docs/design/patterns/KUBERNETES_CONFIGMAP_SECRET_OPERATIONS.md')
    quality_gate = read('scripts/quality_gate.sh')

    require(
        not (ROOT / 'app/kubernetes_operations/secrets/routes.py').exists(),
        'Monolithic Secret routes.py must remain removed.',
        errors,
    )
    for module in ('crud_routes', 'reveal_routes', 'tls_routes'):
        require(
            f'app.kubernetes_operations.secrets.{module}' in operation_routes,
            f'Kubernetes operation routing must import canonical {module}.',
            errors,
        )

    require(
        'filter_current_generation(ConfigurationInventory.query' in overview,
        'Secret overview must use latest committed Configuration generation.',
        errors,
    )
    require(
        'filter_current_generation(PodInventory.query' in impact,
        'Secret impact review must use latest committed Pod generation.',
        errors,
    )
    for token in ('pod_collection_state != COLLECTED', 'pod_operational_state(pod.phase, pod.ready)'):
        require(token in impact, f'Secret impact contract missing token: {token}', errors)

    replace_payloads = read('app/kubernetes_operations/secrets/replace_payloads.py')
    require(
        'validate_secret_size' in create and 'validate_secret_size' in replace_payloads,
        'Create and Replace must share the canonical Secret validation boundary.',
        errors,
    )
    require(
        'scrub_secret_payload(created)' in create,
        'Create must scrub Secret payload material returned by Kubernetes.',
        errors,
    )

    require(
        create.count('create_namespaced_secret(') == 1,
        'Create service must perform exactly one provider call per invocation.',
        errors,
    )
    require(
        "dry_run='All' if dry_run else None" in create,
        'Create service must explicitly select validation or mutation mode.',
        errors,
    )
    require(
        replace.count('_patch_secret(') == 2,
        'Replace service must contain one helper definition and one invocation only.',
        errors,
    )
    require('dry_run=dry_run' in replace, 'Replace service must perform exactly one patch per invocation.', errors)
    require(
        'validate_then_apply(' in crud_routes,
        'Final create/replace must execute one validation call followed by one mutation call.',
        errors,
    )

    require(
        "salt='kaori-secret-delete-validation-v2'" in receipts,
        'Secret delete receipt must use the v2 signed contract.',
        errors,
    )
    for token in ('user_id', 'cluster_id', 'namespace', 'secret_name', 'resource_version'):
        require(token in receipts, f'Secret delete receipt missing binding: {token}', errors)
    require(
        'session' not in receipts and 'SECRET_DELETE_RECEIPT_SESSION_KEY' not in crud_routes,
        'Secret delete receipt must not be stored in session.',
        errors,
    )
    require(
        crud_routes.count('_validate_secret_operation_csrf()') >= 3,
        'Create, Replace, and Delete must enforce CSRF server-side.',
        errors,
    )
    require(
        tls_routes.count('_tls_csrf_guard(') >= 5,
        'Single and bulk TLS preview/apply routes must use the canonical CSRF guard.',
        errors,
    )
    require(
        'kubernetes_tls_secret_csrf_failed' in tls_routes and 'queue_feedback=True' in tls_routes,
        'TLS CSRF failures must be audited and returned through operational feedback.',
        errors,
    )
    for template in ('create.html', 'replace.html', 'delete.html', 'tls_rotate.html', 'tls_rotation.html'):
        require(
            'name="csrf_token"' in read(f'app/templates/kubernetes_operations/secrets/{template}'),
            f'Secret mutation form missing CSRF token: {template}',
            errors,
        )

    require(
        'verify_delete_receipt(' in crud_routes and 'expected_resource_version' in crud_routes,
        'Final Secret delete must verify the signed resource-version receipt.',
        errors,
    )
    require(
        'V1Preconditions(resource_version=resource_version)' in delete,
        'Secret delete must retain the Kubernetes resourceVersion precondition.',
        errors,
    )

    require(
        'impact.display' in delete_target and 'impact.reported' in delete_target,
        'Secret delete UI must distinguish zero references from missing Pod evidence.',
        errors,
    )
    require(
        'Impact and Authorization Preflight' in landing and 'Impact and Dry-Run' not in landing,
        'Secret landing must describe the actual non-destructive delete validation.',
        errors,
    )
    for token in ('data-secret-delete-validation-token', 'data-secret-delete-final-action'):
        require(token in delete_actions, f'Secret delete action contract missing token: {token}', errors)
    require(
        "querySelector('[data-secret-delete-validation-token]')?.remove()" in delete_js,
        'Secret delete target changes must invalidate the signed receipt.',
        errors,
    )

    require(
        'X-Forwarded-For' not in reveal_routes and 'return request.remote_addr' in reveal_routes,
        'Protected Reveal must not parse untrusted forwarding headers inside the route.',
        errors,
    )
    for token in (
        "response.headers['Cache-Control'] = 'no-store, private, max-age=0'",
        "response.headers['Pragma'] = 'no-cache'",
        "response.headers['X-Content-Type-Options'] = 'nosniff'",
        "response.headers['Referrer-Policy'] = 'no-referrer'",
        "response.headers['X-Frame-Options'] = 'DENY'",
        "response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'",
    ):
        require(token in reveal_routes, f'Protected Reveal response missing header: {token}', errors)
    require(
        'components/protected_value_panel.html' in reveal_value,
        'Protected Reveal must use the canonical protected value panel.',
        errors,
    )
    require(
        'filter_current_generation(' in live,
        'Reveal request inventory linkage must use the current committed Secret record.',
        errors,
    )

    require(
        "'cert_bytes':" not in tls_updates and "'key_bytes':" not in tls_updates,
        'TLS preview must never return certificate or private-key bytes to templates.',
        errors,
    )
    require(
        'def preview_uploaded_pair' not in tls_service and 'def apply_certificate_update' not in tls_service,
        'Read-oriented TLS Governance service must not own mutation functions.',
        errors,
    )
    for token in (
        'read_namespaced_secret(',
        "dry_run in ('All', None)",
        "'metadata': {'resourceVersion': resource_version}",
        'scrub_secret_payload(response)',
    ):
        require(token in tls_mutation, f'TLS mutation boundary missing token: {token}', errors)

    require(
        'from app.governance.tls_certificates.service import ' in tls_routes
        and 'get_tls_certificate_detail' in tls_routes
        and 'get_tls_certificate_page' in tls_routes,
        'TLS routes must import the canonical Governance read service directly.',
        errors,
    )
    require(
        'from app.governance.tls_certificates.updates import ' in tls_routes
        and 'apply_bulk_update' in tls_routes
        and 'apply_certificate_update' in tls_routes
        and 'preview_uploaded_pair' in tls_routes,
        'TLS routes must import the canonical Governance update service directly.',
        errors,
    )
    for token in ('provider_updated', 'persistence_confirmed', "'status': 'warning'"):
        require(token in tls_updates, f'TLS update outcome contract missing token: {token}', errors)
    require(
        'apply_bulk_update' not in overview and '__all__' not in overview,
        'Secret overview service must not re-export TLS Governance services.',
        errors,
    )
    require(
        'record_secret_activity as _record_secret_activity' in tls_routes,
        'TLS routes must use canonical operational feedback and Activity Audit.',
        errors,
    )

    for retired_permission in ('tls_certificates.update', 'tls_certificates.bulk_update'):
        require(
            retired_permission not in rbac_defaults,
            f'Retired TLS permission remains in default registry: {retired_permission}',
            errors,
        )
        require(
            retired_permission not in rbac_service,
            f'Retired TLS permission remains in dependency graph: {retired_permission}',
            errors,
        )
        require(
            retired_permission in permission_migration,
            f'Retired TLS permission migration missing: {retired_permission}',
            errors,
        )
    require(
        'kubernetes_secrets.rotate_tls' in permission_migration
        and 'kubernetes_secrets.bulk_rotate_tls' in permission_migration,
        'Retired TLS role assignments must migrate to canonical Secret permissions.',
        errors,
    )
    require(
        'tls_certificates_active_sync' not in governance_routes
        and 'def tls_certificates_active_sync' not in tls_governance_routes,
        'Unused TLS active-sync compatibility endpoint must remain removed.',
        errors,
    )
    require(
        'def collect_tls_certificates(' not in tls_collector,
        'Unused record-only TLS collector wrapper must remain removed.',
        errors,
    )
    require(
        'components/operation_feedback_oob.html'
        in read('app/templates/kubernetes_operations/secrets/_create_operation_result.html'),
        'Secret HTMX operations must use canonical operational feedback OOB.',
        errors,
    )
    require(
        'signed Secret delete receipt' in standard,
        'Secret operations standard must document the signed delete receipt.',
        errors,
    )
    require(
        'verify_secret_management_standard.py' in quality_gate,
        'Secret Management verifier must run in quality gate.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Secret Management audit passed: committed evidence, single provider calls, '
        'stateless user-bound deletion receipt, protected reveal headers, operational feedback, '
        'canonical route ownership, TLS persistence outcomes, and retired-permission cleanup are aligned.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
