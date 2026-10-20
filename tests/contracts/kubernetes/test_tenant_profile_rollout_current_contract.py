"""The Tenant Resource Profile rollout button follows committed matching state (#2381)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_rollout_read_model_reuses_exact_service_predicate_without_provider_calls() -> None:
    registry = read('app/kubernetes/tenant/registry_context.py')
    rollout = read('app/kubernetes/tenant/resource_profile_rollout_context.py')
    service = read('app/kubernetes/tenant/service.py')
    controls = read('app/kubernetes/tenant/resource_profile_controls.py')

    assert (
        'from app.kubernetes.tenant.resource_profile_rollout_context import _resource_profile_rollout_targets'
        in registry
    )
    assert '_resource_profile_rollout_targets = _registry_context._resource_profile_rollout_targets' in service
    assert 'def namespace_allocation_is_current(' in controls
    for field in (
        'resource_profile_version',
        'allocation_quota_json',
        'allocation_limit_defaults_json',
        'allocation_storage_policy_json',
    ):
        assert field in controls

    assert 'namespace_allocation_is_current(record, profile, *desired)' in rollout
    assert '_resource_profile_controls.namespace_allocation_is_current(' in service
    assert 'namespace_allocation_values(profile)' in rollout
    assert '_resource_profile_controls.namespace_allocation_values(profile)' in service
    assert 'load_only(' in rollout
    assert 'TenantNamespace.resource_profile_id.in_(profile_ids)' in rollout
    assert "target['already_current'] = target['eligible'] and target['pending'] == 0" in rollout
    assert "target['eligible'] and target['pending'] == 0" in rollout
    assert 'tenant_workspace_connection_available(' not in rollout.split('def _resource_profile_rollout_targets(', 1)[1]


def test_rollout_form_disables_only_fully_current_selected_native_targets() -> None:
    dialogs = read('app/templates/kubernetes/tenant/partials/_resource_profile_management_dialogs.html')
    js = read('app/static/js/tenant_resource_profile_presets.js')
    registry = read('app/templates/kubernetes/tenant/partials/_resource_profile_registry.html')

    for marker in (
        'data-tenant-profile-rollout-form',
        'data-tenant-profile-rollout-select',
        'data-tenant-profile-rollout-submit',
        'data-rollout-eligible',
        'data-rollout-current',
        'data-rollout-pending',
        'data-rollout-already-current',
        'data-rollout-needs-change',
        'data-rollout-status-message',
        'Already Current',
    ):
        assert marker in dialogs

    assert "target.provider_key != 'native_kubernetes'" in dialogs
    assert 'target.eligible' in dialogs
    assert 'target.already_current' in dialogs
    assert 'disabled\n                                        aria-disabled="true"' in dialogs
    assert "rollout_targets|sum(attribute='pending')" in registry
    assert "rollout_targets|sum(attribute='outdated')" not in registry

    for assertion in (
        "const current = eligible && option?.dataset.rolloutCurrent === 'true'",
        'const disabled = !permitted || !eligible || current',
        'submit.disabled = disabled',
        "submit.setAttribute('aria-disabled', disabled ? 'true' : 'false')",
        "select.addEventListener('change', sync)",
        "form.addEventListener('submit', (event) => {",
        'if (submit.disabled) event.preventDefault()',
        "scope.querySelectorAll('[data-tenant-profile-rollout-form]').forEach(initProfileRolloutForm)",
        "document.addEventListener('htmx:afterSwap'",
    ):
        assert assertion in js

    assert 'Provider drift is checked separately.' in js


def test_server_retains_native_mutation_guards_and_skips_released_history() -> None:
    service = read('app/kubernetes/tenant/service.py')
    routes = read('app/kubernetes/tenant/routes.py')
    assert 'def rollout_resource_profile_to_tenant_committed(' in service
    assert "if tenant.provider_key != 'native_kubernetes':" in service
    assert 'tenant.lifecycle_status != TenantLifecycleStatus.READY.value' in service
    assert 'TenantNamespaceProvisioningStatus.RELEASED.value' in service
    assert "summary['already_current'] += 1" in service
    assert 'change_native_namespace_allocation_committed(' in service
    assert "@permission_required('tenant.manage')" in routes
    assert "@tenant_bp.post('/resource-profiles/<int:profile_id>/rollout')" in routes
    assert '_csrf()' in routes
