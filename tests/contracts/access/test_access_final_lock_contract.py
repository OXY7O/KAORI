from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def _assert_governed_modal_widths(source: str) -> None:
    """Retain steps, governed/membership, and default modal widths in order."""
    width_policy = (
        "'max-w-6xl' if presentation == 'steps' "
        "else 'max-w-3xl' if presentation in ['governed', 'membership'] "
        "else 'max-w-xl'"
    )
    assert width_policy in source


def test_access_final_lock_is_release_gated_and_documented() -> None:
    lock = read('docs/design/KAORI_ACCESS_LOCK_V1.md')
    ownership = read('docs/architecture/ACCESS_OWNERSHIP.md')
    quality_gate = read('scripts/quality_gate.sh')
    verifier = read('scripts/verify_access_final_lock.py')

    assert 'Final Locked — Access v1' in ownership
    assert 'KAORI Access Final Lock v1' in lock
    assert 'python scripts/verify_access_final_lock.py' in quality_gate
    assert "print(f'PASS — KAORI Access Final Lock v1 · {len(templates)} templates')" in verifier
    assert "print('FAIL — KAORI Access Final Lock v1')" in verifier


def test_access_final_lock_preserves_authentication_actor_and_session_security() -> None:
    config = read('app/config/default.py')
    queries = read('app/platform_operations/notifications/queries.py')
    actors = read('app/platform_operations/notifications/actors.py')
    session = read('app/access/authentication/session.py')

    assert 'AUTH_REMEMBER_ME_DAYS = _bounded_env_int(' in config
    assert "'AUTH_REMEMBER_ME_DAYS'," in config
    assert 'REMEMBER_COOKIE_DURATION = timedelta(days=AUTH_REMEMBER_ME_DAYS)' in config
    assert "current_app.config.get('AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME', False)" in session

    assert 'func.count(func.distinct(Notification.actor_key))' in queries
    assert 'Notification.actor_key == normalized_actor_key' in queries
    assert "key='unauthenticated'" in actors
    assert "key='system:kaori'" in actors
    assert 'def actor_snapshot_for_user(' in actors


def test_access_final_lock_protects_content_driven_modal_formatter_boundary() -> None:
    modal = read('app/templates/components/resource_detail_modal.html')

    assert 'h-auto max-h-[calc(100dvh-1rem)]' in modal
    assert 'max-h-[calc(100dvh-1rem) ]' not in modal
    djlint_off = modal.find('{# djlint:off #}')
    dialog_open = modal.find('<section id="{{ dialog_id }}"')
    dialog_close = modal.find('</section>', dialog_open)
    djlint_on = modal.find('{# djlint:on #}')

    assert 0 <= djlint_off < dialog_open < dialog_close < djlint_on


def test_current_access_documents_do_not_reopen_the_locked_ui() -> None:
    current_docs = (
        read('app/access/README.md'),
        read('app/access/users/README.md'),
        read('docs/architecture/ACCESS_OWNERSHIP.md'),
        read('docs/design/KAORI_ACCESS_LOCK_V1.md'),
    )

    for document in current_docs:
        assert 'UI not final locked' not in document
        assert 'not final-lock the UI' not in document


def test_uat4_access_modals_share_header_footer_chrome_without_changing_dialog_bodies() -> None:
    shared = read('app/templates/components/destructive_confirmation_modal.html')
    host = read('app/templates/components/resource_detail_modal.html')
    permissions = read('app/templates/access/permissions/index.html')
    roles = read('app/templates/access/roles/index.html')
    activity = read('app/templates/access/activity_audit/index.html')
    users = read('app/templates/access/users/index.html')

    for page in (permissions, roles, activity):
        assert 'resource_detail_modal.host(' in page
    for label in ('Permission', 'Role', 'Activity'):
        assert f"resource_detail_modal.host('{label}'" in (permissions + roles + activity)
    assert 'data-resource-detail-header-host' in host
    assert 'data-resource-detail-close' in host
    assert 'data-resource-detail-summary-host' in host
    assert 'footer_text' in host

    assert 'access_chrome=false' in shared
    assert "presentation in ['steps', 'kubernetes'] or access_chrome" in shared
    assert 'if access_chrome else' in shared
    assert 'data-destructive-modal-confirm' in shared
    assert 'data-destructive-modal-close' in shared
    assert 'data-submit-button-id="{{ confirm_button_id }}"' in shared
    _assert_governed_modal_widths(shared)
    assert "if presentation == 'steps' else 'space-y-5 p-5'" in shared
    assert 'scope_value }} · Confirmation required' in shared
    assert 'access_chrome=true' in roles and 'access_chrome=true' in users
    assert roles.count('access_chrome=true') == 1
    assert users.count('access_chrome=true') == 1
    assert 'role-delete-confirmation' in roles
    assert 'delete-user-modal' in users


def test_uat5_access_detail_headers_follow_permission_reference_without_body_relayout() -> None:
    permission = read('app/templates/access/permissions/partials/_permission_detail.html')
    role = read('app/templates/access/roles/partials/_role_detail.html')
    activity = read('app/templates/access/activity_audit/partials/_activity_detail.html')
    host = read('app/templates/components/resource_detail_modal.html')
    confirmation = read('app/templates/components/destructive_confirmation_modal.html')

    # Screenshot reference: identity icon, title + state, description, metadata.
    permission_header = permission.split('<header data-resource-detail-header', 1)[1].split('</header>', 1)[0]
    role_header = role.split('<header data-resource-detail-header', 1)[1].split('</header>', 1)[0]
    activity_header = activity.split('<header data-resource-detail-header', 1)[1].split('</header>', 1)[0]
    for header in (permission_header, role_header, activity_header):
        assert 'detail_ui.expanded_workspace_icon_classes()' in header
        assert 'detail_ui.header_identity_row()' in header
        assert header.index('table_label.status_label(') < header.index('mt-1')
        assert header.index('mt-1') < header.index('mt-2 flex min-w-0 flex-wrap items-center')
        assert 'table_label.metadata_label(' in header

    for expression in ('permission.state.label', 'permission.key', 'permission.module_label'):
        assert expression in permission_header
    for expression in ('detail.state_label', 'detail.type_short', 'role.name'):
        assert expression in role_header
    for expression in ('item.status_label', 'item.category_label', 'item.message'):
        assert expression in activity_header

    # The resource detail host retains the shared close button and footer.
    assert 'data-resource-detail-header-host' in host
    assert 'data-resource-detail-summary-host' in host
    assert 'data-resource-detail-close' in host
    assert 'footer_text' in host

    # The Access-only destructive variant adopts the same hierarchy; no false
    # Canonical status for destructive actions, no changed default or dialog body.
    assert 'access_chrome=false' in confirmation
    assert "table_label.status_label('Confirmation Required', 'warning', 'shield-alert', 'detail')" in confirmation
    assert "table_label.metadata_label(scope_value, 'shield-check')" in confirmation
    assert "table_label.metadata_label(action_label, 'archive-x')" in confirmation
    assert "if access_chrome else 'min-w-0'" in confirmation
    _assert_governed_modal_widths(confirmation)
    assert 'data-destructive-modal-confirm' in confirmation
    assert 'data-submit-button-id="{{ confirm_button_id }}"' in confirmation
    assert 'Canonical' not in confirmation


def test_access_administration_form_actions_reuse_canonical_button_variants() -> None:
    from jinja2 import Environment

    cases = (
        ('app/templates/access/users/form.html', 1, 1),
        ('app/templates/access/users/reset_password.html', 1, 1),
        ('app/templates/access/roles/form.html', 3, 1),
        ('app/templates/access/identity_providers/form.html', 1, 2),
    )
    for path, expected_primary, expected_secondary in cases:
        template = read(path)
        Environment().parse(template)
        assert 'components/action_button.html' in template
        assert template.count("action_button.classes('primary')") == expected_primary
        assert template.count("action_button.classes('secondary')") == expected_secondary

    user = read('app/templates/access/users/form.html')
    reset = read('app/templates/access/users/reset_password.html')
    role = read('app/templates/access/roles/form.html')
    provider = read('app/templates/access/identity_providers/form.html')

    for template in (user, reset):
        assert 'form.hidden_tag()' in template
        assert 'data-operation-submit' in template
        assert 'data-loading-label=' in template
    assert 'data-operation-submit-label' in user
    assert 'Reset Password</span>' in reset
    assert 'form.hidden_tag()' in role
    assert 'read_only and can_mutate_role' in role
    assert 'read_only and is_system_role' in role
    assert "page_mode == 'clone'" in role
    assert 'form.hidden_tag()' in provider
    assert "formaction=\"{{ url_for('identity_providers.test_configuration'" in provider
    assert 'formmethod="post"' in provider
    assert 'Test Connection</button>' in provider
    assert 'Save Provider</button>' in provider
