from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_rbac_dependencies_and_access_admin_boundary_are_source_controlled() -> None:
    catalog = read('app/definitions/catalogs/rbac/access.yaml')
    defaults = read('app/rbac/defaults.py')
    service = read('app/rbac/service.py')
    policy = read('app/rbac/policy.py')

    assert 'permission_dependencies:' in catalog
    assert 'access_administration_permissions:' in catalog
    assert 'DEFAULT_PERMISSION_DEPENDENCIES' in defaults
    assert 'ACCESS_ADMINISTRATION_PERMISSIONS' in defaults
    assert '_validate_permission_dependencies' in defaults
    assert 'Permission dependency cycle detected' in defaults
    assert 'PERMISSION_DEPENDENCIES: dict[' not in service
    assert 'DEFAULT_PERMISSION_DEPENDENCIES.get(permission_key' in service
    assert 'def role_is_access_admin_level' in policy
    assert 'ACCESS_ADMINISTRATION_PERMISSIONS' in policy


def test_role_mutation_uses_reserved_defaults_and_delegation_ceiling() -> None:
    service = read('app/access/roles/service.py')
    routes = read('app/access/roles/routes.py')
    policy = read('app/rbac/policy.py')
    form = read('app/access/roles/forms.py')
    template = read('app/templates/access/roles/form.html')

    for required in (
        'def ensure_permission_selection_within_delegation_boundary',
        'def ensure_role_within_delegation_boundary',
        'def validate_custom_role_slug',
        'role_slug_is_reserved(slug)',
        'actor_delegable_permission_keys(actor)',
    ):
        assert required in service
    assert 'def role_is_mutation_protected' in policy
    assert 'role_is_mutation_protected(role)' in routes
    assert 'ensure_role_within_delegation_boundary(actor=actor, role=role)' in routes
    assert 'ensure_permission_selection_within_delegation_boundary(' in service
    assert 'impact_acknowledged = BooleanField' in form
    assert 'Confirm the user and Identity Provider impact before deactivating this referenced role.' in service
    assert 'Delegation Boundary' in template
    assert 'Outside Ceiling' in template
    assert 'permission.id not in delegable_permission_ids' in template


def test_protected_default_integrity_is_catalog_authoritative_and_visible() -> None:
    baseline = read('app/access/roles/baseline.py')
    presentation = read('app/access/roles/presentation.py')
    index = read('app/templates/access/roles/index.html')
    registry = read('app/templates/access/roles/partials/_registry.html')
    detail = read('app/templates/access/roles/partials/_role_detail.html')

    assert 'DEFAULT_ROLE_DEFINITIONS' in baseline
    assert 'DEFAULT_ROLE_PERMISSIONS' in baseline
    assert "key='drift'" in baseline
    assert 'missing_defaults' in baseline
    assert "'baseline_drift_count': baseline_drift_count" in presentation
    assert 'Baseline Drift' in index
    assert '>Baseline</th>' in registry
    assert 'row.baseline.label' in registry
    assert 'Baseline Integrity' in detail
    assert 'detail.baseline_detail' in detail


def test_administrator_level_is_capability_based_not_role_slug_based() -> None:
    policy = read('app/rbac/policy.py')
    user_model = read('app/models/user.py')
    user_service = read('app/users/service.py')
    user_summary = read('app/users/access_summary.py')
    provider_service = read('app/identity_providers/service.py')
    provisioning = read('app/identity_providers/provisioning.py')
    sso = read('app/auth/sso.py')

    assert 'def role_is_access_admin_level' in policy
    assert 'role.permission_keys() & ACCESS_ADMINISTRATION_PERMISSIONS' in policy
    assert 'role_is_access_admin_level(self.role_record)' in user_model
    assert 'role_is_access_admin_level(user.role_record)' in user_service
    assert 'role_is_access_admin_level(role)' in user_summary
    assert 'role_is_access_admin_level(role)' in provider_service
    assert 'role_is_access_admin_level(role)' in provisioning
    assert 'role_is_access_admin_level(role)' in sso
    for source in (user_model, user_service, user_summary, provider_service, provisioning, sso):
        assert "role.name == 'admin'" not in source
        assert "role.name != 'admin'" not in source


def test_access_admin_audit_helper_is_not_owned_by_user_service() -> None:
    helper = read('app/common/admin_audit.py')
    users_service = read('app/users/service.py')
    users_routes = read('app/users/routes.py')
    role_service = read('app/access/roles/service.py')
    provider_routes = read('app/identity_providers/routes.py')

    assert 'def record_admin_event' in helper
    assert 'AuditEvent()' in helper
    assert 'def record_admin_event' not in users_service
    assert 'from app.common.admin_audit import record_admin_event' in users_routes
    assert 'from app.common.admin_audit import record_admin_event' in role_service
    assert 'from app.common.admin_audit import record_admin_event' in provider_routes


def test_identity_provider_catalog_optional_presentation_fields_do_not_break_bootstrap() -> None:
    catalog = read('app/auth/identity_provider/catalog.py')
    definitions = read('app/definitions/catalogs/auth/identity_provider/providers.yaml')

    assert "client_secret_placeholder=require_str(raw, 'client_secret_placeholder', path, allow_empty=True)" in catalog
    assert "guidance_partial=require_str(raw, 'guidance_partial', path, allow_empty=True)" in catalog
    assert "client_secret_placeholder: ''" in definitions
    assert "guidance_partial: ''" in definitions


def test_role_delegation_boundary_applies_to_user_and_identity_provider_assignment() -> None:
    policy = read('app/rbac/policy.py')
    rbac_service = read('app/rbac/service.py')
    user_service = read('app/users/service.py')
    user_routes = read('app/users/routes.py')
    provider_service = read('app/identity_providers/service.py')
    provider_routes = read('app/identity_providers/routes.py')
    provisioning = read('app/identity_providers/provisioning.py')

    assert 'def role_is_delegable_by_actor' in policy
    assert 'ACCESS_ADMINISTRATION_PERMISSIONS' in policy
    assert 'def assignable_roles_for_actor' in rbac_service
    assert 'role_is_delegable_by_actor(actor, role)' in rbac_service
    assert 'def requested_role_assignment_allowed' in user_service
    assert 'role_is_delegable_by_actor(actor, role)' in user_service
    assert 'assign_user_form_choices(form, actor=actor)' in user_routes
    assert 'def provider_default_role_assignment_error' in provider_service
    assert 'assignable_roles_for_actor(actor)' in provider_service
    assert 'provider_default_role_assignment_error(actor, form.default_role_id.data)' in provider_routes
    assert 'assign_projection_role_choices(form, actor=actor)' in provider_routes
    assert 'role_is_delegable_by_actor(actor, role)' in provisioning
    assert 'actor=actor' in provider_routes


def test_identity_provider_permissions_are_independent_from_user_management() -> None:
    catalog = read('app/definitions/catalogs/rbac/access.yaml')
    routes = read('app/identity_providers/routes.py')
    overview = read('app/access/overview/presentation.py')
    sidebar = read('app/templates/components/navigation/access_management_menu.html')
    migration = read('migrations/versions/20260817_identity_provider_rbac_split.py')

    for permission in (
        'identity_providers.view',
        'identity_providers.manage',
        'identity_providers.provision',
    ):
        assert f'- key: {permission}' in catalog
    assert 'identity_providers.manage: [identity_providers.view]' in catalog
    assert 'identity_providers.provision: [identity_providers.view]' in catalog
    assert "@permission_required('identity_providers.view')" in routes
    assert "@permission_required('identity_providers.manage')" in routes
    assert "@permission_required('identity_providers.provision')" in routes
    assert "_can('identity_providers.view')" in overview
    assert "current_user.has_permission('identity_providers.view')" in sidebar
    assert "revision = '20260817_idp_rbac_split'" in migration
    assert "down_revision = '20260817_identity_provider_v1'" in migration
    assert "permissions.c.key == 'users.manage'" in migration
    assert '_copy_role_assignments' in migration
