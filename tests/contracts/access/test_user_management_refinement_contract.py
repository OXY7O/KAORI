from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_user_restore_returns_to_inactive_administration() -> None:
    service = read('app/users/service.py')
    routes = read('app/users/routes.py')
    assert 'def restore_user(target: User)' in service
    restore_block = service.split('def restore_user(target: User)', 1)[1].split('def record_admin_event', 1)[0]
    assert 'target.deleted_at = None' in restore_block
    assert 'target.account_is_active = False' in restore_block
    assert 'target.account_is_active = True' not in restore_block
    assert 'returned to inactive administration and must be activated explicitly' in routes


def test_last_super_admin_mutations_use_transaction_safe_boundary() -> None:
    service = read('app/users/service.py')
    routes = read('app/users/routes.py')
    assert 'def lock_active_super_admin_boundary(target: User)' in service
    assert '.with_for_update()' in service
    assert 'db.session.refresh(target)' in service
    assert 'removes_active_super_admin_authority = bool(' in routes
    assert routes.count('lock_active_super_admin_boundary(user)') >= 3
    assert 'The last active Local Database super admin cannot be deactivated.' in service
    assert 'The last active Local Database super admin cannot be deleted.' in service
    assert 'The last active Local Database super admin cannot lose the super admin flag.' in service


def test_user_management_hero_matches_inventory_hero_contract() -> None:
    template = read('app/templates/users/partials/_hero.html')
    directory = read('app/users/directory.py')
    routes = read('app/users/routes.py')
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
    summary = read('app/templates/users/partials/_summary_cards.html')
    directory = read('app/users/directory.py')
    assert 'Account &amp; Identity Posture' in summary
    assert 'grid gap-px bg-outline-subtle md:grid-cols-2 xl:grid-cols-4' in summary
    assert 'border-t border-outline-subtle bg-surface-hover' in summary
    for label in ('Active Accounts', 'Inactive Accounts', 'Access Findings', 'Local Super Admins'):
        assert label in summary
    for label in ('Local Database', 'LDAP Directory', 'SSO Providers', 'Deleted & Restore'):
        assert label in summary
    assert 'Restore returns Deleted → Inactive' in summary
    assert 'never reactivates access' in summary
    assert "'deleted': int(deleted_users or 0)" in directory


def test_user_directory_uses_shared_kaori_loading_filters_labels_and_expand_details() -> None:
    content = read('app/templates/users/partials/_content.html')
    filters = read('app/templates/users/partials/_filters.html')
    table = read('app/templates/users/partials/_table.html')
    detail = read('app/templates/users/partials/_user_detail.html')
    assert '{% import "components/loading_bar.html" as loading_bar %}' in content
    assert "loading_bar.render('users-refresh-indicator'" in content
    assert '{% import "components/table.html" as table_ui %}' in filters
    assert 'table_ui.filter_select_classes()' in filters
    assert 'Clear Filters' not in filters
    assert 'Local Database' in filters
    assert '· Inactive' in filters
    assert 'lg:grid-cols-4' in filters
    assert 'lg:grid-cols-[' not in filters
    assert '{% import "components/details/_expandable_row.html" as expandable %}' in table
    assert 'expandable.toggle_button' in table
    assert 'expandable.static_detail_row' in table
    assert 'Identity Source' in table
    assert 'Last Authentication' in table
    assert 'Emergency Access' in table
    assert 'Administrative Actions' in detail
    assert 'No Administrative Action' in detail


def test_user_directory_pagination_uses_current_kaori_rows_and_previous_next_contract() -> None:
    table = read('app/templates/users/partials/_table.html')
    assert (
        "Showing {{ pagination.start_item }}–{{ pagination.end_item }} of {{ pagination.total_items }} {{ pagination_ui.resource_name('Users', pagination.total_items) }}"
        in table
    )
    assert '>Rows</span>' in table
    assert 'aria-label="Rows Per Page"' in table
    assert 'Previous' in table
    assert 'Next' in table
    assert 'pagination_ui.numeric_pages(' in table
    assert "hx_target='#users-page-content'" in table


def test_user_delete_uses_shared_destructive_confirmation_component() -> None:
    index = read('app/templates/users/index.html')
    detail = read('app/templates/users/partials/_user_detail.html')
    modal = read('app/templates/components/destructive_confirmation_modal.html')
    script = read('app/static/js/destructive_confirmation_modal.js')
    assert not (ROOT / 'app/templates/users/partials/_delete_modal.html').exists()
    assert '{% import "components/destructive_confirmation_modal.html" as destructive_confirmation %}' in index
    assert 'destructive_confirmation.render(' in index
    assert 'destructive_confirmation_modal.js' in index
    assert 'data-destructive-submit-button-id' in detail
    assert 'data-destructive-scope' in detail
    assert 'opener?.dataset.destructiveSubmitButtonId' in script
    assert 'button.dataset.destructiveScope' in script
    assert "notice='This final action cannot be reversed by KAORI.'" in modal


def test_user_management_keeps_dual_audit_ledger_until_shared_audit_consumers_are_migrated() -> None:
    service = read('app/users/service.py')
    readme = read('app/users/README.md')
    assert 'AuditEvent' in service and 'Role' in service and 'User' in service
    assert 'def record_admin_event(' in service
    assert 'Legacy AuditEvent Boundary' in readme
    assert 'must not be removed from User Management in isolation' in readme


def test_password_reset_revokes_existing_sessions_through_credential_generation() -> None:
    readme = read('app/users/README.md')
    model = read('app/models/user.py')
    login_extension = read('app/extensions/login.py')
    assert 'Password Reset Session Boundary' in readme
    assert 'User.auth_session_version' in readme
    assert 'revoke all existing authenticated sessions and remembered sign-ins' in readme
    assert 'auth_session_version' in model
    assert 'issued_session_version != current_session_version' in login_extension


def test_reset_password_matches_kaori_hero_impact_and_secure_delivery_contract() -> None:
    template = read('app/templates/users/reset_password.html')
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
        'app/templates/users/form.html': 2,
        'app/templates/users/reset_password.html': 1,
        'app/templates/users/providers/partials/_provider_guidance.html': 1,
        'app/templates/users/external_identities.html': 1,
        'app/templates/access/roles/form.html': 1,
    }
    for path, minimum in required.items():
        source = read(path)
        assert source.count('xl:sticky xl:top-5') >= minimum, path
    for path in required:
        assert 'xl:top-6' not in read(path), path

    for full_width_page in (
        'app/templates/access/roles/index.html',
        'app/templates/access/permissions/index.html',
    ):
        assert 'xl:sticky xl:top-5' not in read(full_width_page), full_width_page
