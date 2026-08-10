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
    collector = read('app/governance/tls_certificates/collector.py')
    service = read('app/governance/tls_certificates/service.py')
    mutation = read('app/governance/tls_certificates/mutation.py')
    updates = read('app/governance/tls_certificates/updates.py')
    routes = read('app/governance/tls_certificates/routes.py')
    tasks = read('app/governance/tls_certificates/tasks.py')
    presentation = read('app/governance/tls_certificates/job_presentation.py')
    workspace = read('app/templates/governance/tls_certificates/partials/_page_workspace.html')
    progress = read('app/templates/governance/tls_certificates/partials/_sync_progress_toast.html')
    table = read('app/templates/governance/tls_certificates/partials/_table.html')
    detail = read('app/templates/governance/tls_certificates/partials/_detail_content.html')
    single_rotation = read('app/templates/kubernetes_operations/secrets/tls_rotate.html')
    bulk_rotation = read('app/templates/kubernetes_operations/secrets/tls_rotation.html')
    tls_routes = read('app/kubernetes_operations/secrets/tls_routes.py')
    readme = read('app/governance/tls_certificates/README.md')
    standard = read('docs/design/patterns/KUBERNETES_TLS_CERTIFICATE_GOVERNANCE.md')
    audit = read('docs/design/audits/KUBERNETES_TLS_NOTIFICATION_DELIVERY_AUDIT_2026_08.md')
    quality_gate = read('scripts/quality_gate.sh')

    for token in (
        'class TLSCollectionEvidence',
        'secret_collection_status',
        'ingress_mapping_status',
        'def _has_secret_identity(',
        'unique_consumers:',
        'Unexpected Kubernetes collection failure.',
        'if secret.type == TLS_SECRET_TYPE and _has_secret_identity(secret)',
    ):
        require(token in collector, f'TLS collector missing canonical evidence token: {token}', errors)
    require(
        "str(exc) or 'Kubernetes collection failed.'" not in collector,
        'TLS collector must not expose raw unexpected provider errors.',
        errors,
    )

    for token in (
        'class TLSClusterSyncResult',
        'fatal_error: str | None',
        'warning: str | None',
        'warning_cluster_count',
    ):
        require(token in service or token in tasks, f'TLS sync outcome missing evidence-aware token: {token}', errors)

    for source_name, source in (
        ('service.py', service),
        ('updates.py', updates),
        ('mutation.py', mutation),
    ):
        require(
            '.query.get(' not in source,
            f'TLS canonical module still uses legacy Model.query.get(): {source_name}',
            errors,
        )

    for token in (
        'read_namespaced_secret(',
        "for dry_run in ('All', None)",
        "'metadata': {'resourceVersion': resource_version}",
        'scrub_secret_payload(response)',
        'scrub_mapping_values(encoded_data)',
    ):
        require(token in mutation, f'TLS mutation boundary missing token: {token}', errors)

    require(
        'provider_updated' in updates and 'persistence_confirmed' in updates,
        'TLS rotation must distinguish provider mutation from KAORI persistence.',
        errors,
    )
    require(
        "'status': 'warning'" in updates,
        'TLS rotation must report provider-success/persistence-gap as warning.',
        errors,
    )

    require(
        'id="tls-certificates-page-workspace"' in workspace,
        'TLS page must use one canonical workspace boundary.',
        errors,
    )
    require(
        "partial_mode='page_workspace'" in workspace,
        'TLS background refresh must request the canonical workspace.',
        errors,
    )
    require('_sync_progress_toast.html' in workspace, 'TLS workspace must own the canonical progress toast.', errors)
    require(
        'components/operational_progress_toast.html' in progress,
        'TLS progress must reuse the global progress-toast component.',
        errors,
    )
    require(
        'caption class="sr-only"' in table and 'scope="col"' in table,
        'TLS registry table must retain accessibility boundaries.',
        errors,
    )
    for token in ('coverage_reported', 'ingress_mapping_reported', 'Not Reported'):
        require(token in detail or token in table, f'TLS UI missing evidence semantic token: {token}', errors)

    for token in (
        'Certificate File',
        'Private Key File',
        'tls.crt',
        'tls.key',
        'border border-outline-default bg-surface-hover p-4',
        'border border-dashed border-outline-strong bg-surface-card',
        'Validate Before Update',
    ):
        require(token in single_rotation, f'Single TLS rotation missing canonical upload/action token: {token}', errors)
    require(
        'TLS Certificate Validation Completed' in tls_routes,
        'TLS rotation notifications must preserve TLS acronym and Title Case.',
        errors,
    )
    for template_name, source in (
        ('single TLS rotation', single_rotation),
        ('bulk TLS rotation', bulk_rotation),
    ):
        require(
            'type="file"' in source and 'class="hidden"' in source,
            f'{template_name} file pickers must keep native inputs out of the scroll/focus layout.',
            errors,
        )
        require(
            'class="sr-only"' not in source,
            f'{template_name} must not use focusable sr-only native file inputs that can shift the viewport.',
            errors,
        )
        require(
            'preventScroll: true' in source,
            f'{template_name} file picker focus restoration must prevent page jumping.',
            errors,
        )
        require(
            '@click.prevent="$refs.' in source,
            f'{template_name} file picker must use an explicit non-submit chooser button.',
            errors,
        )

    require('queue_transient_feedback(' in routes, 'TLS queued acknowledgement must remain transient.', errors)
    require('OperationalDeliveryPolicy.PERSISTENT' in routes, 'TLS sync blockers must remain persistent.', errors)
    require(
        'deck_user_ids = _notify_requesters(' in tasks,
        'TLS worker must persist terminal Notification Deck rows.',
        errors,
    )
    require(
        tasks.index('deck_user_ids = _notify_requesters(') < tasks.index('context.succeed('),
        'TLS terminal Notification Deck persistence must precede successful job closure.',
        errors,
    )
    require(
        "'notification_deck_user_ids'" in tasks and "'activity_audit_saved'" in tasks,
        'TLS job result must record terminal delivery persistence.',
        errors,
    )
    require(
        'notification_deck_visible = user_id is not None and' in presentation,
        'TLS terminal toast must use requester-specific Deck persistence evidence.',
        errors,
    )

    obsolete = (
        'app/governance/tls_certificates/toast.py',
        'app/templates/governance/tls_certificates/partials/_inventory_scope.html',
        'app/templates/governance/tls_certificates/partials/_content.html',
        'app/templates/governance/tls_certificates/partials/_sync_toast.html',
    )
    for relative in obsolete:
        require(not (ROOT / relative).exists(), f'Legacy TLS file must remain removed: {relative}', errors)

    require(
        'Operational feedback and Notification Deck' in readme,
        'TLS module README must document terminal delivery ownership.',
        errors,
    )
    require(
        'Toast and Notification Deck policy' in standard, 'TLS design standard must document delivery policy.', errors
    )
    for token in ('`audit_only`', '`deck_on_failure`', '`persistent`', '20260805_notification_deck_v2'):
        require(token in audit, f'TLS notification delivery audit missing token: {token}', errors)
    require(
        'verify_tls_certificate_governance_standard.py' in quality_gate,
        'TLS Governance verifier must run in quality gate.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI TLS Certificate Governance audit passed: collection evidence, data minimization, '
        'resource-version mutation, canonical workspace, progress toast, terminal Deck delivery, '
        'and legacy removal are aligned.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
