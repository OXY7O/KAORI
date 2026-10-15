"""Release/Handoff provider composition must remain acyclic and fail closed."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TENANT = ROOT / 'app/kubernetes/tenant'

APPROVAL_OPS = (
    'build_capsule_handoff_worklist',
    'native_handoff_execution_history',
    'native_handoff_readback_history',
    'readback_proves_handoff_not_started',
    '_source_history',
    '_verify_original_provider_state',
    'require_authorized_no_transfer_restart',
)
FINALIZATION_OPS = (
    '_read_resource',
    'latest_native_handoff_execution',
    '_latest_native_dry_run',
    'verify_external_native_component',
    'latest_native_successor_acceptance',
    '_plan_hash',
    'latest_release_handoff_approval',
    'latest_release_handoff_plan',
)


def test_authoritative_tenant_operations_are_composed_by_application() -> None:
    bootstrap = (ROOT / 'app/bootstrap/blueprints.py').read_text(encoding='utf-8')
    approval = (TENANT / 'release_handoff_approval.py').read_text(encoding='utf-8')
    preflight = (TENANT / 'release_preflight.py').read_text(encoding='utf-8')
    assert "app.extensions['kaori_tenant_handoff_operations'] = {" in bootstrap
    for name in APPROVAL_OPS:
        assert f"'{name}': {name}" in bootstrap
        assert f"require_handoff_operation('{name}')" in approval
    for name in FINALIZATION_OPS:
        assert f"'{name}': {name}" in bootstrap
        assert f"require_handoff_operation('{name}')" in preflight


def test_no_reverse_tenant_imports_from_approval_and_release_preflight() -> None:
    approval = (TENANT / 'release_handoff_approval.py').read_text(encoding='utf-8')
    preflight = (TENANT / 'release_preflight.py').read_text(encoding='utf-8')
    assert 'from app.kubernetes.tenant.capsule_handoff_worklist import' not in approval
    assert 'from app.kubernetes.tenant.native_handoff_executor import' not in approval
    assert 'from app.kubernetes.tenant.native_no_transfer_recovery import' not in approval
    assert 'from app.kubernetes.tenant.release_handoff_approval import' not in preflight
    assert 'from app.kubernetes.tenant.native_handoff_executor import' not in preflight


def test_missing_handoff_operation_fails_closed_instead_of_empty_evidence() -> None:
    resolver = (TENANT / 'handoff_runtime_operations.py').read_text(encoding='utf-8')
    assert "current_app.extensions.get('kaori_tenant_handoff_operations')" in resolver
    assert "raise RuntimeError('Tenant Handoff operations are not registered.')" in resolver
    assert 'if not callable(operation):' in resolver
