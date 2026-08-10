from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_secret_management_uses_canonical_split_route_ownership() -> None:
    operation_routes = read('app/kubernetes_operations/routes.py')

    assert not (ROOT / 'app/kubernetes_operations/secrets/routes.py').exists()
    for module in ('crud_routes', 'reveal_routes', 'tls_routes'):
        assert f'app.kubernetes_operations.secrets.{module}' in operation_routes
    assert not (ROOT / 'tests/kubernetes_operations/test_secret_delete_workflow.py').exists()
    tls_routes = read('app/kubernetes_operations/secrets/tls_routes.py')
    overview = read('app/kubernetes_operations/secrets/service.py')
    assert 'from app.governance.tls_certificates.service import' in tls_routes
    assert 'get_tls_certificate_detail' in tls_routes and 'get_tls_certificate_page' in tls_routes
    assert 'apply_bulk_update' not in overview and '__all__' not in overview
    tls_service = read('app/governance/tls_certificates/service.py')
    tls_updates = read('app/governance/tls_certificates/updates.py')
    tls_mutation = read('app/governance/tls_certificates/mutation.py')
    assert "'cert_bytes':" not in tls_updates and "'key_bytes':" not in tls_updates
    assert 'def preview_uploaded_pair' not in tls_service
    assert 'def apply_certificate_update' not in tls_service
    assert 'from app.governance.tls_certificates.updates import' in tls_routes
    assert all(
        name in tls_routes for name in ('apply_bulk_update', 'apply_certificate_update', 'preview_uploaded_pair')
    )
    assert 'read_namespaced_secret(' in tls_mutation
    assert "for dry_run in ('All', None)" in tls_mutation
    assert "'metadata': {'resourceVersion': resource_version}" in tls_mutation


def test_secret_create_replace_and_delete_have_single_provider_boundaries() -> None:
    create = read('app/kubernetes_operations/secrets/create_service.py')
    replace = read('app/kubernetes_operations/secrets/replace_service.py')
    delete = read('app/kubernetes_operations/secrets/delete_service.py')
    crud = read('app/kubernetes_operations/secrets/crud_routes.py')
    receipts = read('app/kubernetes_operations/secrets/receipts.py')

    assert create.count('create_namespaced_secret(') == 1
    assert "dry_run='All' if dry_run else None" in create
    assert 'scrub_secret_payload(created)' in create
    assert replace.count('_patch_secret(') == 2
    assert 'dry_run=dry_run' in replace
    assert 'validate_then_apply(' in crud
    assert 'verify_delete_receipt(' in crud
    assert 'session' not in receipts
    assert "salt='kaori-secret-delete-validation-v2'" in receipts
    assert 'V1Preconditions(resource_version=resource_version)' in delete
    assert crud.count('_validate_secret_operation_csrf()') >= 3
    tls_routes = read('app/kubernetes_operations/secrets/tls_routes.py')
    assert tls_routes.count('_tls_csrf_guard(') >= 5
    assert 'kubernetes_tls_secret_csrf_failed' in tls_routes
    for template in ('create.html', 'replace.html', 'delete.html', 'tls_rotate.html', 'tls_rotation.html'):
        assert 'name="csrf_token"' in read(f'app/templates/kubernetes_operations/secrets/{template}')


def test_secret_evidence_and_protected_reveal_boundaries_are_explicit() -> None:
    overview = read('app/kubernetes_operations/secrets/service.py')
    impact = read('app/kubernetes_operations/secrets/impact.py')
    live = read('app/kubernetes_operations/secrets/live_service.py')
    reveal = read('app/kubernetes_operations/secrets/reveal_routes.py')

    assert 'filter_current_generation(ConfigurationInventory.query' in overview
    assert 'filter_current_generation(PodInventory.query' in impact
    assert 'pod_collection_state != COLLECTED' in impact
    assert 'filter_current_generation(' in live
    assert 'X-Forwarded-For' not in reveal
    for header in (
        "Cache-Control'] = 'no-store, private, max-age=0'",
        "Referrer-Policy'] = 'no-referrer'",
        "X-Frame-Options'] = 'DENY'",
        "Cross-Origin-Resource-Policy'] = 'same-origin'",
    ):
        assert header in reveal


def test_secret_validation_and_feedback_are_shared_canonical_components() -> None:
    create = read('app/kubernetes_operations/secrets/create_service.py')
    replace_payloads = read('app/kubernetes_operations/secrets/replace_payloads.py')
    validation = read('app/kubernetes_operations/secrets/validation.py')
    support = read('app/kubernetes_operations/secrets/route_support.py')
    choice = read('app/templates/components/choice_card_group.html')

    for token in (
        'validate_secret_size',
        'validate_data_key',
        'validate_ssh_private_key',
    ):
        assert token in validation
        assert token in create or token in replace_payloads
    assert 'record_operational_activity' in support
    assert 'SecretActivityOptions' in support
    assert 'border border-brand-outline bg-kaori-soft' in choice


def test_retired_tls_permission_and_sync_compatibility_paths_are_removed() -> None:
    defaults = read('app/rbac/defaults.py')
    dependencies = read('app/rbac/service.py')
    migration = read('migrations/versions/20260805_secret_ops_v2.py')
    governance_routes = read('app/governance/routes.py')
    tls_routes = read('app/governance/tls_certificates/routes.py')
    collector = read('app/governance/tls_certificates/collector.py')

    for key in ('tls_certificates.update', 'tls_certificates.bulk_update'):
        assert key not in defaults
        assert key not in dependencies
        assert key in migration
    assert 'kubernetes_secrets.rotate_tls' in migration
    assert 'kubernetes_secrets.bulk_rotate_tls' in migration
    assert 'tls_certificates_active_sync' not in governance_routes
    assert 'def tls_certificates_active_sync' not in tls_routes
    assert 'def collect_tls_certificates(' not in collector
