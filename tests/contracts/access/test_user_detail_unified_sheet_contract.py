"""User Directory expanded evidence uses the approved unified KAORI resource sheet."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_user_detail_is_one_compact_full_width_resource_sheet() -> None:
    detail = source('app/templates/access/users/partials/_user_detail.html')
    shared = source('app/templates/components/details/_detail_content.html')

    Environment().parse(detail)
    assert 'data-user-detail-workspace' in detail
    assert 'data-kaori-user-detail-layout="unified-resource-sheet"' in detail
    assert detail.count('detail_ui.resource_sheet()') == 1
    assert detail.count('detail_ui.inventory_section(') == 5
    assert detail.count('compact_layout=true') == 5
    assert 'data-kaori-unified-resource-sheet' in shared
    assert 'data-kaori-inventory-section-layout="resource-sheet-band"' in shared
    assert 'xl:grid-cols-2' not in detail
    assert 'rounded-xl border border-outline-default bg-surface-card p-4' not in detail
    assert detail.count('{% call ') == detail.count('{% endcall %}')

    sections = (
        "'Identity', 'contact'",
        "'Authentication', 'fingerprint'",
        "'Authorization', 'shield-check'",
        "'Lifecycle', 'history'",
        "'Administrative Actions', 'settings-2'",
    )
    assert [detail.index(x) for x in sections] == sorted(detail.index(x) for x in sections)


def test_identity_and_authentication_evidence_is_retained() -> None:
    detail = source('app/templates/access/users/partials/_user_detail.html')
    for evidence in (
        'user.id',
        'user.username',
        'user.display_name',
        'user.email',
        'user_view.source.label',
        'identity_context.credential_owner',
        'identity_context.provider_name',
        'identity_context.identity_state',
        'identity_context.identity_tone',
        'user.last_login_at|user_datetime("Never")',
        'identity_context.credential_detail',
    ):
        assert evidence in detail

    assert 'data-kaori-user-identity-facts' in detail
    assert 'data-kaori-user-authentication-facts' in detail
    assert 'sm:grid-cols-2' in detail
    assert "stacked_detail_row('Email', user.email, break_all=true)" in detail
    # Email and Display Name must share the same two-column Identity row.
    identity = detail.split('data-kaori-user-identity-facts>', 1)[1].split('{% endcall %}', 1)[0]
    assert 'sm:grid-cols-2' in detail.split('data-kaori-user-identity-facts>', 1)[0].split('<div class="grid')[-1]
    assert "stacked_detail_row('Display Name'," in identity
    assert "stacked_detail_row('Email'," in identity
    assert 'sm:col-span-2' not in identity
    assert 'data-kaori-user-credential-boundary' in detail
    assert 'max-w-4xl break-words text-sm leading-6' in detail


def test_authorization_and_lifecycle_long_values_have_readable_rows() -> None:
    detail = source('app/templates/access/users/partials/_user_detail.html')

    for evidence in (
        'user_view.role.label',
        'user_view.role.state_label',
        "'Enabled' if user.is_super_admin else 'Disabled'",
        'user_view.access.label',
        'user_view.access.tone',
        'user_view.access.reason',
        'user_view.lifecycle.label',
        'user.created_at|user_datetime("-")',
        'user.updated_at|user_datetime("-")',
        'user.deleted_at|user_datetime("Not Deleted")',
    ):
        assert evidence in detail
    assert 'data-kaori-user-authorization-facts' in detail
    assert 'data-kaori-user-effective-access' in detail
    assert 'data-kaori-user-lifecycle-facts' in detail
    assert 'max-w-4xl flex-1 break-words text-sm leading-6' in detail


def test_user_detail_uses_adaptive_grids_without_empty_right_columns() -> None:
    detail = source('app/templates/access/users/partials/_user_detail.html')
    Environment().parse(detail)

    def fact_grid(marker: str) -> tuple[str, str]:
        # Inspect each specific grid and its content, not unrelated sibling bands.
        header = detail.split(f'data-kaori-user-{marker}-facts>', 1)[0]
        classes = header.rsplit('<div class="', 1)[1].split('"', 1)[0]
        fields = detail.split(f'data-kaori-user-{marker}-facts>', 1)[1].split('{% endcall %}', 1)[0]
        return classes, fields

    identity_classes, identity = fact_grid('identity')
    assert 'sm:grid-cols-2' in identity_classes
    assert 'lg:grid-cols-3' not in identity_classes
    assert identity.index("stacked_detail_row('Display Name'") < identity.index("stacked_detail_row('Email'")
    assert 'sm:col-span-2' not in identity
    assert "stacked_detail_row('Email', user.email, break_all=true)" in identity

    auth_classes, authentication = fact_grid('authentication')
    assert 'sm:grid-cols-2' in auth_classes
    assert 'lg:grid-cols-3' in auth_classes
    assert (
        authentication.index('Identity Source')
        < authentication.index('Credential Owner')
        < authentication.index("'Provider'")
    )
    assert 'lg:col-span-2' in authentication
    assert "stacked_detail_row('Last Authentication'," in authentication

    authorization_classes, authorization = fact_grid('authorization')
    assert 'sm:grid-cols-2' in authorization_classes
    assert 'lg:grid-cols-3' in authorization_classes
    for label in ('Assigned Role', 'Role State', 'Emergency Access'):
        assert label in authorization

    lifecycle_classes, lifecycle = fact_grid('lifecycle')
    assert 'sm:grid-cols-2' in lifecycle_classes
    assert 'lg:grid-cols-4' in lifecycle_classes
    for label in ('Account State', 'Created', 'Updated', 'Deleted'):
        assert label in lifecycle

    assert 'data-kaori-user-credential-boundary' in detail
    assert 'data-kaori-user-effective-access' in detail
    assert 'max-w-4xl break-words text-sm leading-6' in detail
    assert 'max-w-4xl flex-1 break-words text-sm leading-6' in detail
    assert 'gap-2 lg:justify-end' in detail


def test_user_actions_stay_guarded_without_duplicate_edit() -> None:
    detail = source('app/templates/access/users/partials/_user_detail.html')
    table = source('app/templates/access/users/partials/_table.html')
    assert 'data-kaori-user-detail-actions' in detail
    assert "url_for('users.edit', user_id=user.id)" not in detail
    assert "url_for('users.edit', user_id=user.id)" in table
    assert "actions.get('can_edit')" in table

    for permission in (
        'can_reset_password',
        'can_restore',
        'can_deactivate',
        'can_activate',
        'can_delete',
    ):
        assert f"actions.get('{permission}')" in detail
    for contract in (
        "url_for('users.reset_password', user_id=user.id)",
        "url_for('users.restore', user_id=user.id)",
        "url_for('users.deactivate', user_id=user.id)",
        "url_for('users.activate', user_id=user.id)",
        "url_for('users.delete', user_id=user.id)",
        'hx-target="#users-page-content"',
        'hx-include="#users-filter-form"',
        'hx-indicator="#users-refresh-indicator"',
        'csrf_token()',
        'data-destructive-modal-open',
        'data-destructive-modal-id="delete-user-modal"',
        'data-destructive-submit-button-id',
        'data-destructive-target',
        'data-destructive-scope',
        'No Additional Actions',
    ):
        assert contract in detail
    assert detail.count('{% if ') == detail.count('{% endif %}')


def test_user_compact_toggle_keeps_shared_expandable_contract() -> None:
    table = source('app/templates/access/users/partials/_table.html')
    macro_source = source('app/templates/components/details/_expandable_row.html')
    assert "open_label='Details', close_label='Hide Details', compact=true" in table
    assert 'expandable.static_detail_row(detail_row_id, detail_target_id, 6)' in table
    assert 'compact=false' in macro_source
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
    toggle = env.get_template('components/details/_expandable_row.html').module.toggle_button

    compact = str(
        toggle(
            'users',
            2,
            '',
            'user-detail-content-2',
            'user-detail-row-2',
            open_label='Details',
            close_label='Hide Details',
            compact=True,
        )
    )
    normal = str(toggle('roles', 3, '', 'role-detail-content-3', 'role-detail-row-3'))

    for attribute in (
        'data-detail-toggle',
        'data-detail-group="users"',
        'data-detail-item="2"',
        'data-detail-target="user-detail-content-2"',
        'data-detail-row="user-detail-row-2"',
        'data-detail-open-label="Details"',
        'data-detail-close-label="Hide Details"',
        'data-detail-toggle-label',
        'data-detail-chevron',
        'data-detail-leading-icon',
        'aria-expanded="false"',
        'aria-controls="user-detail-row-2"',
    ):
        assert attribute in compact
    assert 'min-h-9' in compact
    assert 'shadow-sm' not in compact
    assert 'data-detail-open-label="View Details"' in normal
    assert 'data-detail-close-label="Close Details"' in normal
    assert 'min-h-10' in normal
    assert 'shadow-sm' in normal


def test_uat6_user_detail_left_headers_use_source_backed_labels() -> None:
    detail = source('app/templates/access/users/partials/_user_detail.html')
    shared = source('app/templates/components/details/_detail_content.html')
    Environment().parse(detail)
    for title, icon, description, badge in (
        ('Identity', 'contact', 'Committed account identity', 'user_view.source.label'),
        (
            'Authentication',
            'fingerprint',
            'Identity authority and credential ownership',
            'identity_context.credential_owner',
        ),
        (
            'Authorization',
            'shield-check',
            'Effective local role and access state',
            'user_view.access.label',
        ),
    ):
        marker = f"'{title}', '{icon}',"
        section = detail.split(marker, 1)[1].split('compact_layout=true', 1)[0]
        assert f"description='{description}'" in section
        assert f'badge={badge}' in section
    authorization = detail.split("'Authorization', 'shield-check',", 1)[1].split('compact_layout=true', 1)[0]
    assert "badge_type='status', badge_tone=user_view.access.tone" in authorization
    assert 'badge=user_view.role.label' not in detail
    assert 'detail_ui.inventory_section(' in detail
    assert detail.count('detail_ui.inventory_section(') == 5
    assert 'data-kaori-user-identity-facts' in detail
    assert 'data-kaori-user-authentication-facts' in detail
    assert 'data-kaori-user-authorization-facts' in detail
    # Shared macro already places the badge under the description at xl.
    assert 'mt-3 hidden xl:flex' in shared
    assert 'table_label.metadata_label(badge' in shared
    assert 'table_label.status_label(badge, badge_tone' in shared


def test_directory_credential_boundary_copy_is_concise_and_authoritative() -> None:
    context = source('app/access/users/directory.py')
    detail = source('app/templates/access/users/partials/_user_detail.html')
    assert 'Directory verifies passwords; KAORI manages identity links and access.' in context
    assert 'The directory validates the password; KAORI stores only' not in context
    assert 'identity_context.credential_detail' in detail
    assert 'data-kaori-user-credential-boundary' in detail
