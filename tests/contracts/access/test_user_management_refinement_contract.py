import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_user_restore_returns_to_inactive_administration() -> None:
    service = read('app/access/users/service.py')
    routes = read('app/access/users/routes.py')
    assert 'def restore_user(target: User)' in service
    restore_block = service.split('def restore_user(target: User)', 1)[1]
    assert 'target.deleted_at = None' in restore_block
    assert 'target.account_is_active = False' in restore_block
    assert 'target.account_is_active = True' not in restore_block
    assert 'returned to inactive administration and must be activated explicitly' in routes


def test_last_super_admin_mutations_use_transaction_safe_boundary() -> None:
    service = read('app/access/users/service.py')
    routes = read('app/access/users/routes.py')
    assert 'def lock_active_super_admin_boundary(target: User)' in service
    assert '.with_for_update()' in service
    assert 'db.session.refresh(target)' in service
    assert 'removes_active_super_admin_authority = bool(' in routes
    assert routes.count('lock_active_super_admin_boundary(user)') >= 3
    assert 'The last active Local Database super admin cannot be deactivated.' in service
    assert 'The last active Local Database super admin cannot be deleted.' in service
    assert 'The last active Local Database super admin cannot lose the super admin flag.' in service


def test_user_management_hero_matches_inventory_hero_contract() -> None:
    template = read('app/templates/access/users/partials/_hero.html')
    directory = read('app/access/users/directory.py')
    routes = read('app/access/users/routes.py')
    assert 'page_hero.context_card(' in template
    assert 'page_hero.context_panel_classes()' not in template
    assert "'Identity & Access'" in template
    assert "'User Posture'" in template
    assert 'summary.posture_label' in template
    assert 'summary.posture_tone' in template
    assert "('circle-check', 'Active Accounts'" in template
    assert "('shield-alert', 'Access Findings'" in template
    assert "hero_action_label = 'Add User' if can_manage_users else 'View User Directory'" in template
    assert "hero_action_href = url_for('users.create') if can_manage_users else '#user-directory'" in template
    assert "'managed': int(access_summary['total']) + int(deleted_users or 0)" in directory
    assert 'access_summary = build_user_access_summary()' in directory
    assert 'hero_oob=True' in routes
    assert 'hx-swap-oob="outerHTML"' in template


def test_user_management_posture_matches_permission_registry_overview_structure() -> None:
    summary = read('app/templates/access/users/partials/_summary_cards.html')
    directory = read('app/access/users/directory.py')
    assert 'Account &amp; Identity Posture' in summary
    assert 'grid gap-px bg-outline-subtle md:grid-cols-2 xl:grid-cols-4' in summary
    assert 'border-t border-outline-subtle bg-surface-hover' in summary
    for label in ('Active Accounts', 'Inactive Accounts', 'Access Findings', 'Local Super Admins'):
        assert label in summary
    for label in ('Local Database', 'Directory', 'SSO Providers', 'Deleted & Restore'):
        assert label in summary
    assert 'Restore: Deleted → Inactive' in summary
    assert 'manual activation' in summary
    assert "'deleted': int(deleted_users or 0)" in directory


def test_user_directory_uses_shared_kaori_loading_filters_labels_and_expand_details() -> None:
    content = read('app/templates/access/users/partials/_content.html')
    directory = read('app/templates/access/users/partials/_directory.html')
    filters = read('app/templates/access/users/partials/_filters.html')
    table = read('app/templates/access/users/partials/_table.html')
    detail = read('app/templates/access/users/partials/_user_detail.html')
    assert '{% include "access/users/partials/_directory.html" %}' in content
    assert '{% import "components/loading_bar.html" as loading_bar %}' in directory
    assert "loading_bar.render('users-refresh-indicator'" in directory
    assert "registry_ui.clear_filters_link('users.index'" in directory
    assert '{% import "components/table.html" as table_ui %}' in filters
    assert 'table_ui.filter_select_classes()' in filters
    assert 'Clear Filters' not in filters
    assert 'Local Database' in filters
    assert '· Inactive' in filters
    assert 'registry_ui.filter_form(' in filters
    shared_registry = read('app/templates/components/table_registry.html')
    assert 'table_primitives.filter_layout_classes()' in shared_registry
    assert 'data-kaori-canonical-registry-filter' in shared_registry
    assert 'lg:grid-cols-' not in filters
    assert '{% import "components/details/_expandable_row.html" as expandable %}' in table
    assert 'expandable.toggle_button' in table
    assert 'expandable.static_detail_row' in table
    assert 'Identity Source' in table
    assert 'Last Authentication' in table
    assert 'Emergency Access' in table
    assert 'Administrative Actions' in detail
    # The approved fallback is shown only when none of the five governed
    # administrative actions is authorized for the viewed account.
    assert 'No Additional Actions' in detail
    assert "not actions.get('can_reset_password') and not actions.get('can_restore')" in detail
    assert "and not actions.get('can_activate') and not actions.get('can_deactivate')" in detail
    assert "and not actions.get('can_delete') %}" in detail


def test_user_directory_pagination_uses_current_kaori_rows_and_previous_next_contract() -> None:
    table = read('app/templates/access/users/partials/_table.html')
    footer = read('app/templates/components/table_registry.html')
    assert "registry_ui.footer('users.index'" in table
    for required in (
        "'user-directory'",
        "'users-refresh-indicator'",
        "resource_label='Users'",
        "rows_aria_label='Rows Per Page'",
        "control_name='user-directory'",
    ):
        assert required in table
    for required in (
        'Showing {{ pagination.start_item }}–{{ pagination.end_item }} of {{ pagination.total_items }}',
        '<span>Rows</span>',
        'aria-label="{{ rows_aria_label }}"',
        'Previous',
        'Next',
        'pagination_ui.numeric_pages(',
        'hx-indicator="#{{ loading_id }}"',
        'data-kaori-canonical-registry-pagination',
    ):
        assert required in footer


def test_user_delete_uses_shared_destructive_confirmation_component() -> None:
    index = read('app/templates/access/users/index.html')
    detail = read('app/templates/access/users/partials/_user_detail.html')
    modal = read('app/templates/components/destructive_confirmation_modal.html')
    script = read('app/static/js/destructive_confirmation_modal.js')
    assert not (ROOT / 'app/templates/access/users/partials/_delete_modal.html').exists()
    assert '{% import "components/destructive_confirmation_modal.html" as destructive_confirmation %}' in index
    assert 'destructive_confirmation.render(' in index
    assert 'destructive_confirmation_modal.js' in index
    assert 'data-destructive-submit-button-id' in detail
    assert 'data-destructive-scope' in detail
    assert 'opener?.dataset.destructiveSubmitButtonId' in script
    assert 'button.dataset.destructiveScope' in script
    assert "notice='This final action cannot be reversed by KAORI.'" in modal


def test_access_administration_uses_shared_persisted_audit_helper() -> None:
    service = read('app/access/users/service.py')
    routes = read('app/access/users/routes.py')
    helper = read('app/common/admin_audit.py')
    readme = read('app/access/users/README.md')
    assert 'def record_admin_event(' not in service
    assert 'from app.common.admin_audit import record_admin_event' in service
    assert 'record_admin_event' not in routes
    assert 'AuditEvent()' in helper
    assert 'Shared Administrative Audit Boundary' in readme
    assert 'app/common/admin_audit.py' in readme


def test_password_reset_revokes_existing_sessions_through_credential_generation() -> None:
    readme = read('app/access/users/README.md')
    model = read('app/models/user.py')
    login_extension = read('app/extensions/login.py')
    assert 'Password Reset Session Boundary' in readme
    assert 'User.auth_session_version' in readme
    assert 'revoke all existing authenticated sessions and remembered sign-ins' in readme
    assert 'auth_session_version' in model
    assert 'issued_session_version != current_session_version' in login_extension


def test_reset_password_matches_kaori_hero_impact_and_secure_delivery_contract() -> None:
    template = read('app/templates/access/users/reset_password.html')
    assert 'page_hero.context_card(' in template
    assert 'page_hero.context_panel_classes()' not in template
    assert "'Identity & Access'" in template
    assert "'Reset Scope'" in template
    assert "'Eligible'" in template
    assert "('database', 'Credential Owner', 'KAORI'" in template
    assert "'Account State'" in template
    assert '{% import "components/view_more_content.html" as view_more %}' in template
    assert 'view_more.render(' in template
    assert "'Reset Impact'" in template
    assert 'open_by_default=false' in template
    assert "closed_label='View Details'" in template
    assert 'Credential, lifecycle, audit, and session effects.' in template
    assert 'Password Hash' in template
    assert 'Account &amp; Role' in template
    assert 'Activity Audit' in template
    assert 'Existing Sessions' in template
    assert 'Revoked on Next Request' in template
    assert 'Existing sessions and remembered sign-ins for the target account will be revoked.' in template
    assert 'Deliver the new password through an approved secure channel.' not in template


def test_access_main_right_rails_are_sticky_with_shared_desktop_offset() -> None:
    # Sticky is required when a page intentionally keeps a main-content right rail.
    # Full-width registry pages must not retain an empty rail only to satisfy this contract.
    required = {
        'app/templates/access/users/form.html': 2,
        'app/templates/access/users/reset_password.html': 1,
        'app/templates/access/identity_providers/partials/_provider_guidance.html': 1,
        'app/templates/access/roles/form.html': 1,
    }
    for path, minimum in required.items():
        source = read(path)
        assert source.count('xl:sticky xl:top-5') >= minimum, path

    directory = read('app/templates/access/identity_providers/directory_provisioning.html')
    shared_rail = read('app/templates/components/form_with_context_rail.html')
    assert '{% import "components/form_with_context_rail.html" as form_context %}' in directory
    assert 'form_context.rail_classes()' in directory
    assert 'xl:sticky xl:top-5' in shared_rail
    for path in required:
        assert 'xl:top-6' not in read(path), path

    for full_width_page in (
        'app/templates/access/roles/index.html',
        'app/templates/access/permissions/index.html',
    ):
        assert 'xl:sticky xl:top-5' not in read(full_width_page), full_width_page


def test_reset_password_reuses_shared_security_surface_authority() -> None:
    template_path = 'app/templates/access/users/reset_password.html'
    template = read(template_path)
    baseline = json.loads(read('docs/architecture/ui-style-debt-baseline.json'))

    assert 'components/operational_section_card.html' in template
    assert template.count('operational_section_card.shell_classes()') == 2
    assert 'components/operational_callout.html' in template
    assert "operational_callout.semantic_surface_classes('critical')" in template
    assert "operational_callout.semantic_border_classes('critical')" in template
    assert "operational_callout.semantic_surface_classes('normal' if user.account_is_active else 'warning')" in template
    assert "operational_callout.semantic_surface_classes('warning')" in template
    assert "operational_callout.semantic_border_classes('warning')" in template
    assert "operational_callout.semantic_surface_classes('normal')" in template

    assert 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm' not in template
    for direct_border in (
        'border-status-normal-border',
        'border-status-warning-border',
        'border-status-critical-border',
    ):
        assert direct_border not in template

    assert 'form.hidden_tag()' in template
    assert 'Minimum 12 characters' in template
    assert 'data-operation-submit' in template
    assert 'data-loading-label="Resetting password..."' in template
    assert 'sessions revoked on next request' in template
    assert 'Activity Audit logged' in template
    assert 'Role, active state, Super Admin, and external identity links unchanged.' in template
    assert 'Use the recovery workflow owned by the authoritative identity source.' in template
    assert "Use Google's account-recovery process." in template
    assert 'Recover access through GitHub.' in template
    assert 'xl:sticky xl:top-5' in template
    assert template_path not in baseline['files']


def test_reset_password_laptop_copy_density_preserves_security_semantics() -> None:
    import re

    from jinja2 import Environment

    template = read('app/templates/access/users/reset_password.html')
    Environment().parse(template)
    expected = (
        ('Use 12+ characters, a unique passphrase, and no default passwords.', 72),
        (
            'Hash replaced; sessions revoked on next request; Activity Audit logged. '
            'Role, active state, Super Admin, and external identity links unchanged.',
            150,
        ),
        ('KAORI owns local password hashes and audited resets.', 70),
        ('Sessions and remembered sign-ins are invalidated on next request.', 80),
        (
            'Reset at the authoritative directory. KAORI stores identity links '
            'and authorization, not external passwords.',
            115,
        ),
        ('RBAC role and admin tier remain; hash and session generation change.', 75),
    )
    for copy, budget in expected:
        assert len(copy) <= budget
        assert template.count(copy) == 1
        caption = re.search(r'<p class="([^"]+)">\s*' + re.escape(copy), template)
        assert caption, copy
        assert 'text-xs leading-5' in caption.group(1)
        assert not any(token in caption.group(1) for token in ('whitespace-nowrap', 'truncate', 'line-clamp'))

    for preserved in (
        'Minimum 12 characters',
        'form.hidden_tag()',
        "operational_callout.semantic_surface_classes('warning')",
        "operational_callout.semantic_surface_classes('normal')",
        'Revoked on Next Request',
        'Reset Password',
        "Use Google's account-recovery process.",
        'Recover access through GitHub.',
    ):
        assert preserved in template


def test_uat_user_lifecycle_controls_use_shared_protected_header_geometry() -> None:
    form = read('app/templates/access/users/form.html')
    scope = form.split('Lifecycle & Administrative Controls', 1)[1].split(
        "{% if mode == 'edit' and user and user.is_super_admin %}", 1
    )[0]
    assert scope.count('rounded-lg border border-brand-outline bg-kaori-soft px-3.5') == 3
    assert 'for="{{ form.role_id.id }}"' in scope
    assert '{{ form.role_id(class=' in scope
    assert '{{ form.is_active(class=' in scope
    assert '{{ form.is_super_admin(class=' in scope
    assert 'can_manage_admin_fields and super_admin_eligible' in scope
    assert 'Super Admin unavailable' in scope
    for copy in (
        'Admin roles require Super Admin.',
        'Allows sign-in when the provider is ready; disabling retains the account.',
        'Local Database break-glass authority; the last active Super Admin stays protected.',
    ):
        assert copy in scope
    assert 'Role, active state, and administrative tier are presented with the same control structure.' not in scope
    assert 'bg-surface-elevated px-3.5' not in scope
    assert 'text-kaori-strong' in scope
    # Shared violet geometry must not change actual super-admin eligibility or safeguards.
    assert "mode == 'edit' and user and user.is_super_admin" in form
    assert 'Protected Super Admin Account' in form
    assert 'last active Local Database super admin remains protected' in form


def test_uat4_user_create_copy_is_compact_and_canonical() -> None:
    form = read('app/templates/access/users/form.html')
    assert 'Optional; defaults to username.' not in form
    assert 'Assigns post-login RBAC permissions.' not in form
    assert '12+ characters; use a unique passphrase.' not in form
    assert 'KAORI owns local passwords; Directory and SSO use provider-owned admission.' in form
    assert "Use the provider's admission workflow." in form
    assert 'Identity and authorization stay separate.' in form
    assert 'Provider sign-in; KAORI governs roles and lifecycle.' in form
    assert (
        '<strong class="font-semibold text-content-secondary">Assigned Role</strong> sets KAORI permissions after sign-in.'
        in form
    )
    assert (
        '<strong class="font-semibold text-content-secondary">Active Account</strong> gates Local, Directory and SSO access.'
        in form
    )
    assert (
        '<strong class="font-semibold text-content-secondary">Super Admin</strong> is Local Database-only, never Directory/SSO; keep one active.'
        in form
    )
    assert 'if not can_manage_admin_fields' in form
    assert 'Admin roles require Super Admin.' in form
    assert 'can_manage_admin_fields and super_admin_eligible' in form
    assert '{{ form.role_id(class=' in form
    assert '{{ form.display_name(class=' in form
    assert '{{ form.is_super_admin(class=' in form
    assert 'whitespace-nowrap' not in form


def test_uat6_user_edit_copy_balances_context_specific_credential_text() -> None:
    form = read('app/templates/access/users/form.html')
    directory = read('app/access/users/directory.py')

    # Credential Detail is the long, authoritative two-line explanation in
    # User Detail; the narrower violet edit card has a separate short caption.
    assert (
        "'KAORI stores the local password hash and manages resets through its governed, audited workflow.'" in directory
    )
    assert '"KAORI owns local password hashes and resets." if user.auth_source == "database"' in form
    assert 'else identity_context.credential_detail' in form
    assert '{{ identity_context.credential_detail }}' in form

    # Edit User: two-line-friendly link/boundary and 01/02 step descriptions.
    assert 'Review account state, source and role.' in form
    assert 'KAORI owns Local Database credentials, audited resets, and the account access lifecycle.' in form
    assert (
        'Identity profile</strong> updates username, display name and contact email without changing credential ownership.'
        in form
    )
    assert (
        'Assigned Role</strong> changes KAORI RBAC permissions without modifying upstream identity or authentication credentials.'
        in form
    )
    assert 'Identity profile updates the KAORI display name' not in form
    assert 'Assigned Role</strong> changes RBAC permissions without changing the upstream identity.' not in form

    # Do not relax the unchanged edit guards, projection/read authority or URL.
    assert "identity_context.source_family == 'directory'" in form
    assert "current_user.has_permission('identity_providers.view')" in form
    assert "user.auth_source == 'database'" in form
    assert "url_for('users.index')" in form
    assert 'can_manage_admin_fields and super_admin_eligible' in form
    assert 'whitespace-nowrap' not in form


def test_uat_review2_user_form_guide_and_delete_copy() -> None:
    from jinja2 import Environment

    form = read('app/templates/access/users/form.html')
    users = read('app/templates/access/users/index.html')
    Environment().parse(form)
    Environment().parse(users)

    assert '{% import "components/info_tip.html" as info_tip %}' in form
    assert "info_tip.render('add-user-credential-guide'," in form
    assert "variant='guide'" in form
    assert "placement='right'" in form
    assert "if mode == 'create'" in form
    assert 'Use at least 12 characters and a unique passphrase.' in form
    assert 'Confirm the initial password exactly before creating the account.' in form
    assert '12+ characters; use a unique passphrase.</p>' not in form
    assert 'Repeat the initial password exactly before submitting the account.</p>' not in form
    assert 'autocomplete="new-password"' in form
    assert 'form.confirm_password(' in form
    assert 'Minimum 12 characters' in form
    assert 'form.password(' in form
    assert 'KAORI changes enter Activity Audit.' in form
    assert 'Manage external identity providers and admission.' in form
    assert 'Login access will be disabled while Activity Audit history remains retained.' not in users
    assert 'Deletion disables login but retains Activity Audit.' in users
    assert 'Restore returns the account to Inactive; activation remains separate.' in users
    assert "destructive_confirmation.render('delete-user-modal'," in users


def test_uat_review2_edit_profile_guide_and_user_registry_copy() -> None:
    from jinja2 import Environment

    form = read('app/templates/access/users/form.html')
    users = read('app/templates/access/users/index.html')
    Environment().parse(form)
    Environment().parse(users)
    assert 'Review account state, source and role.' in form
    assert 'KAORI owns Local Database credentials, audited resets, and the account access lifecycle.' in form
    assert "info_tip.render('edit-user-self-access-guide'," in form
    assert 'Own access controls are locked.' in form
    assert 'Profile metadata may be updated, but your own role, active state' in form
    assert "variant='guide'" in form
    assert '{% if is_self_edit %}' in form
    assert "notice='Soft delete; restoration is governed.'" in users
    assert 'Deletion disables login but retains Activity Audit.' in users
    assert 'Restore returns the account to Inactive; activation remains separate.' in users
    assert 'whitespace-nowrap' not in users


def test_review3_local_database_credential_boundary_targets_two_desktop_lines() -> None:
    from jinja2 import Environment

    template = read('app/templates/access/users/form.html')
    Environment().parse(template)
    boundary = 'KAORI owns Local Database credentials, audited resets, and the account access lifecycle.'
    assert template.count(boundary) == 1
    assert "user.auth_source == 'database'" in template
    assert "related_page_card.render('User Registry'" in template
    assert 'whitespace-nowrap' not in template
    assert len(boundary) >= 75


def test_access_user_and_reset_password_fields_keep_explicit_labels() -> None:
    from jinja2 import Environment

    entries = (
        (
            'app/templates/access/users/form.html',
            (
                ('Username', 'username'),
                ('Email', 'email'),
                ('Display Name', 'display_name'),
                ('Initial Password', 'password'),
                ('Confirm Password', 'confirm_password'),
            ),
        ),
        (
            'app/templates/access/users/reset_password.html',
            (
                ('New password', 'password'),
                ('Confirm password', 'confirm_password'),
            ),
        ),
    )
    for path, labels in entries:
        template = read(path)
        Environment().parse(template)
        for label, field_name in labels:
            expected = (
                f'<label for="{{{{ form.{field_name}.id }}}}" '
                'class="mb-1.5 block text-sm font-semibold text-content-primary">'
                f'{label}</label>'
            )
            assert len(re.findall(re.escape(expected).replace(r'\ ', r'\s+'), template)) == 1

    user_form = read('app/templates/access/users/form.html')
    reset_form = read('app/templates/access/users/reset_password.html')
    assert 'for="{{ form.role_id.id }}"' in user_form
    assert 'form.hidden_tag()' in user_form
    assert 'form.hidden_tag()' in reset_form
    assert 'data-operation-submit' in user_form
    assert 'data-operation-submit' in reset_form
