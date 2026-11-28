"""Session policy form and authenticated-shell warning contract (#5283)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_warning_is_server_deadline_backed_and_uses_native_dialog() -> None:
    dialog = read('app/templates/access/authentication/partials/_session_expiry_dialog.html')
    layout = read('app/templates/layouts/app.html')
    script = read('app/static/js/session_lifecycle.js')
    Environment().parse(dialog)
    Environment().parse(layout)
    assert 'g.kaori_session_deadlines is defined' in layout
    assert "filename='js/session_lifecycle.js'" in layout
    assert 'kaori-native-dialog' in dialog
    assert 'aria-labelledby="kaori-session-expiry-title"' in dialog
    assert 'aria-describedby="kaori-session-expiry-description"' in dialog
    assert "url_for('auth.session_status')" in dialog
    assert "url_for('auth.session_activity')" in dialog
    assert "url_for('auth.logout')" in dialog
    assert 'name="csrf_token"' in dialog
    assert 'dialog.showModal()' in script
    assert "event.isTrusted" in script
    assert "if (document.visibilityState === 'visible') void synchronize()" in script
    assert 'void synchronize(true)' in script
    assert "method: activity ? 'POST' : 'GET'" in script
    assert "'X-CSRFToken': csrf" in script
    assert 'absoluteSoon || seconds === 0' in script
    assert 'payload.absolute_remaining_seconds' in script
    assert 'payload.idle_remaining_seconds' in script
    assert 'if (response.status === 401)' in script
    assert 'beforeunload' not in script
    assert 'setInterval(() => synchronize(true)' not in script


def test_policy_write_is_permission_guarded_and_transactional() -> None:
    source = read('app/access/authentication_security/__init__.py')
    policy = source.split("@bp.post('/session/policy')", 1)[1].split("@bp.post('/mfa/policy')", 1)[0]
    assert "@permission_required('identity_providers.manage')" in policy
    assert 'validate_csrf(' in policy
    assert 'acknowledge_session_policy_impact' in policy
    assert 'SessionPolicy(' in policy
    assert 'with_for_update=True' in policy
    assert 'changed = previous != requested' in policy
    assert 'auth_session_version=func.coalesce(User.auth_session_version, 1) + 1' in policy
    assert 'auth_session_issued_at=None' in policy
    assert 'auth_session_activity_at=None' in policy
    assert 'stage_authentication_security_event(' in policy
    assert 'previous_policy=asdict(previous)' in policy
    assert 'next_policy=asdict(requested)' in policy
    assert policy.index('db.session.commit()') < policy.index('logout_user()')
    assert 'db.session.rollback()' in policy
