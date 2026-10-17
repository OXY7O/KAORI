from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


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
        assert f"resource_detail_modal.host('{label}'" in (
            permissions + roles + activity
        )
    assert 'data-resource-detail-header-host' in host
    assert 'data-resource-detail-close' in host
    assert 'data-resource-detail-summary-host' in host
    assert 'footer_text' in host

    assert 'access_chrome=false' in shared
    assert 'presentation in [\'steps\', \'kubernetes\'] or access_chrome' in shared
    assert 'if access_chrome else' in shared
    assert 'data-destructive-modal-confirm' in shared
    assert 'data-destructive-modal-close' in shared
    assert 'data-submit-button-id="{{ confirm_button_id }}"' in shared
    assert "if presentation == 'steps' else 'max-w-xl'" in shared
    assert "if presentation == 'steps' else 'space-y-5 p-5'" in shared
    assert 'scope_value }} · Confirmation required' in shared
    assert "access_chrome=true" in roles and "access_chrome=true" in users
    assert roles.count('access_chrome=true') == 1
    assert users.count('access_chrome=true') == 1
    assert 'role-delete-confirmation' in roles
    assert 'delete-user-modal' in users
