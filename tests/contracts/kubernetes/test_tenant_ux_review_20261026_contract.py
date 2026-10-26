"""UAT visual contracts for membership, grant, credential and provider evidence refinements."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
PARTIALS = ROOT / 'app/templates/kubernetes/tenant/partials'


def read(partial: str) -> str:
    return (PARTIALS / partial).read_text(encoding='utf-8')


def test_membership_and_credential_issuance_do_not_repeat_form_headings() -> None:
    memberships = read('_tenant_memberships_workspace.html')
    credentials = read('_tenant_credentials_workspace.html')
    assert 'id="membership-actions"' in memberships
    assert 'aria-label="Membership actions"' in memberships
    assert 'membership-actions-heading' not in memberships
    assert 'id="credential-issuance"' in credentials
    assert 'aria-label="Credential issuance"' in credentials
    assert 'credential-issuance-heading' not in credentials


def test_membership_revoke_requires_confirmed_destructive_action() -> None:
    registry = read('_membership_registry.html')
    assert 'data-destructive-modal-open' in registry
    assert 'data-destructive-submit-button-id="tenant-membership-revoke-submit-' in registry
    assert 'type="submit"' in registry
    assert 'class="hidden"' in registry
    assert "destructive_modal.render('tenant-membership-revoke-modal'" in registry
    assert "url_for('tenant.revoke_membership_route'" in registry
    assert 'name="csrf_token"' in registry
    assert "membership.principal_type in ['user', 'group']" in registry
    assert "membership.principal_type not in ['user', 'group']" in registry
    assert 'Reactivation unavailable' in registry
    assert 'Reactivation requires permission' in registry
    assert "button_text='Reactivate'" in registry
    assert "variant='action'" in registry
    assert "trigger_icon='user-check'" in registry
    assert "button_classes=table_ui.action_classes() ~ ' opacity-60 !cursor-help'" in registry
    assert 'membership-reactivate-permission-' not in registry
    assert "placement='left'" in registry
    assert "action=\"{{ url_for('tenant.reactivate_membership_route'" in registry
    assert "{% if can_manage and membership.principal_type in ['user', 'group'] %}" in registry


def test_governed_confirmation_templates_compile_as_jinja() -> None:
    """Check actual Jinja syntax, not just matching block names or HTML tags."""
    environment = Environment(autoescape=True)
    templates = (
        ROOT / 'app/templates/components/destructive_confirmation_modal.html',
        PARTIALS / '_group_registry.html',
        PARTIALS / '_membership_registry.html',
    )
    for template in templates:
        environment.parse(template.read_text(encoding='utf-8'))

    # A mistyped closing delimiter ({% ... %> rather than {% ... %})
    # must be rejected before a Tenant Groups page can return HTTP 500.
    modal = templates[0].read_text(encoding='utf-8')
    assert '%>' not in modal


def test_governed_confirmation_standard_is_reused_by_membership_and_group() -> None:
    membership = read('_membership_registry.html')
    group = read('_group_registry.html')
    shared = (ROOT / 'app/templates/components/destructive_confirmation_modal.html').read_text(encoding='utf-8')

    for registry in (membership, group):
        assert "presentation='governed'" in registry
        assert 'impact_items=[' in registry
        assert 'warning=' in registry
        assert 'destructive_modal.render(' in registry
        assert 'data-destructive-modal-open' in registry

    assert "operation_kind='revoke'" in membership
    assert "operation_kind='retire'" in group
    assert "target_label='Principal'" in membership
    assert "target_label='Group'" in group
    assert "scope_label='Tenant'" in membership
    assert "scope_label='Tenant / Group'" in group

    assert "max-w-3xl' if presentation in ['governed', 'membership']" in shared
    assert "{% if presentation in ['governed', 'membership'] %}" in shared
    assert 'aria-label="Governed action impact"' in shared
    assert 'divide-y divide-outline-subtle' in shared
    assert '{{ target_label }}' in shared
    assert '{{ scope_label }}' in shared
    assert '{{ warning }}' in shared
    assert 'Important before confirming' in shared
    assert 'data-destructive-target-name' in shared
    assert 'data-destructive-target-scope' in shared
    assert 'data-destructive-modal-confirm' in shared
    assert 'data-submit-button-id="{{ confirm_button_id }}"' in shared
    assert 'data-destructive-modal-close' in shared
    assert "presentation == 'kubernetes'" in shared
    assert "presentation == 'steps'" in shared
    assert 'access_chrome=false' in shared


def test_group_modals_use_distinct_context_and_destructive_review() -> None:
    registry = read('_group_registry.html')
    assert 'aria-label="Tenant information"' in registry
    assert 'aria-label="Group details"' in registry
    assert 'Updating Kubernetes Group Subject' in registry
    assert 'Retire Tenant Group' in registry
    assert "operation_kind='retire'" in registry
    assert "presentation='governed'" in registry
    assert 'data-destructive-modal-open' in registry
    assert 'data-tenant-group-edit-form' in registry


def test_access_grant_and_credential_actions_are_in_expanded_evidence() -> None:
    for table_name, detail_name in (
        ('_access_grant_registry.html', '_access_grant_row_detail.html'),
        ('_credential_registry.html', '_credential_row_detail.html'),
    ):
        table = read(table_name)
        detail = read(detail_name)
        assert 'detail_row.toggle_button(' in table
        assert 'detail_row.static_detail_row(' in table
        assert 'View Details' in table
        assert detail_name in table
        assert 'data-kaori-native-dialog' not in detail
        assert 'hx-target="#tenant-admin-workspace"' in detail
        assert 'hx-disabled-elt="find button"' in detail
        assert 'name="csrf_token"' in detail

    grant = read('_access_grant_row_detail.html')
    credential = read('_credential_row_detail.html')
    assert 'tenant.reconcile_access_grant_route' in grant
    assert 'tenant.revoke_access_grant_route' in grant
    assert 'access-grant-more-actions-' not in read('_access_grant_registry.html')
    for route in (
        'renew_credential_route',
        'resume_credential_route',
        'suspend_credential_route',
        'revoke_credential_route',
    ):
        assert route in credential
    assert 'credential-more-actions-' not in read('_credential_registry.html')
    assert 'one_time_secret.request_dialog' in read('_credential_registry.html')


def test_access_grant_detail_has_compact_context_and_right_aligned_actions() -> None:
    detail = read('_access_grant_row_detail.html')
    group = read('_group_registry.html')

    assert 'aria-label="Selected Access Grant"' in detail
    assert 'aria-label="Governed grant actions"' in detail
    assert 'Grant Context' in detail
    assert 'Governed Actions' in detail
    assert 'lg:grid-cols-[minmax(0,1fr)_minmax(19rem,0.8fr)]' in detail
    assert "action_button.classes('secondary')" in detail
    assert "action_button.classes('critical')" in detail
    assert "action_button.classes('secondary', full=true)" not in detail
    assert "action_button.classes('critical', full=true)" not in detail
    assert detail.count('class="mt-3 flex justify-end"') == 2
    assert detail.count('name="csrf_token"') == 2
    assert detail.count('name="access_inventory_view" value="grants"') == 2
    assert 'tenant.reconcile_access_grant_route' in detail
    assert 'tenant.revoke_access_grant_route' in detail
    assert "if grant.status == 'active'" in detail
    assert 'Retire requires revoked Memberships and reconciled grants.' in group
    assert 'Retirement is blocked while active Memberships' not in group


def test_capsule_and_native_loading_bars_follow_owning_header() -> None:
    for provider in ('_external_capsule_access_inventory.html', '_native_namespace_rbac_inventory.html'):
        template = read(provider)
        assert 'components/loading_bar.html' in template
        assert 'data-tenant-provider-evidence-loading' in template
        assert template.index('data-tenant-provider-evidence-loading') < template.index('Inspection Target')
        assert 'Refreshing committed evidence…' not in template
        assert 'registry_ui.filter_form(' in template
        assert 'registry_ui.footer(' in template


def test_unavailable_namespace_scope_does_not_echo_long_credential_identity() -> None:
    registry = read('_namespace_access_registry.html')
    detail = read('_namespace_access_detail.html')
    assert "access.get('namespace') or 'No Namespace Scope'" in registry
    assert 'detail_row.static_detail_row(' in registry
    assert '_namespace_access_detail.html' in registry
    assert 'data-tenant-namespace-access-detail' in detail
    assert "access.get('service_account_name')" in detail
    assert 'min-w-[1400px]' not in registry
