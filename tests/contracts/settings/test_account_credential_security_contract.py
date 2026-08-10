from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_local_database_password_policy_is_shared_and_matches_settings_copy() -> None:
    policy = read('app/auth/password_policy.py')
    auth_forms = read('app/auth/forms.py')
    user_forms = read('app/users/forms.py')
    settings_template = read('app/templates/settings/account/partials/_change_password.html')
    user_template = read('app/templates/users/form.html')
    reset_template = read('app/templates/users/reset_password.html')
    admin_command = read('app/commands/admin.py')

    assert 'LOCAL_PASSWORD_MIN_LENGTH = 12' in policy
    assert 'LOCAL_PASSWORD_MAX_LENGTH = 1024' in policy
    assert 'class LocalPasswordPolicy:' in policy
    assert 'LocalPasswordPolicy()' in auth_forms
    assert user_forms.count('LocalPasswordPolicy()') >= 2
    assert 'local_password_policy_error(normalized)' in admin_command
    assert 'Minimum 12 characters' in settings_template
    assert 'Minimum 12 characters' in user_template
    assert 'Minimum 12 characters' in reset_template
    assert 'Minimum 8 characters' not in settings_template
    assert 'Minimum eight characters' not in user_template


def test_password_change_advances_session_generation_and_preserves_only_current_browser() -> None:
    model = read('app/models/user.py')
    session_source = read('app/auth/session.py')
    login_extension = read('app/extensions/login.py')
    settings_routes = read('app/settings/routes.py')
    migration = read('migrations/versions/20260809_auth_session_generation.py')

    assert 'auth_session_version: Mapped[int]' in model
    assert "return f'{self.id}:{version}'" in model
    assert 'self.auth_session_version = current_version + 1 if had_local_password else current_version' in model
    assert 'def parse_authenticated_user_identifier(' in session_source
    assert 'def preserve_current_session_after_password_change(' in session_source
    assert "session['_user_id'] = user.get_id()" in session_source
    assert "session['_remember'] = 'clear'" in session_source
    assert 'parse_authenticated_user_identifier(user_id)' in login_extension
    assert 'issued_session_version != current_session_version' in login_extension
    assert 'current_session_version != 1' in login_extension
    assert 'preserve_current_session_after_password_change(user)' in settings_routes
    assert "'session_effect': 'other_sessions_revoked'" in settings_routes
    assert "'remembered_sign_ins': 'revoked'" in settings_routes
    assert "revision = '20260809_auth_session_generation'" in migration
    assert "down_revision = '20260808_data_lifecycle_ops'" in migration


def test_self_service_password_change_rejects_current_password_reuse_and_audits_rejections() -> None:
    routes = read('app/settings/routes.py')

    assert 'def _record_password_change_rejection(' in routes
    assert 'delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY' in routes
    assert "reason_code='current_password_mismatch'" in routes
    assert 'elif user.check_password(new_password):' in routes
    assert 'New password must be different from the current password.' in routes
    assert "reason_code='current_password_reuse'" in routes


def test_credential_workspace_explains_session_effect_without_reopening_external_provider_ownership() -> None:
    change_password = read('app/templates/settings/account/partials/_change_password.html')
    credential_information = read('app/templates/settings/account/partials/_credential_information.html')
    hero = read('app/templates/settings/account/partials/_hero.html')

    assert 'Minimum 12 characters' in change_password
    assert 'Password reuse is blocked' in change_password
    assert 'Session Handling' in credential_information
    assert 'Revoke Others' in credential_information
    assert 'Keep current browser' in credential_information
    assert 'Rotate Sessions' in credential_information
    assert 'Revoke other sessions and remembered sign-ins.' in credential_information
    assert 'Session Outcome' not in credential_information
    assert 'Other Active Sessions' not in credential_information
    assert 'Remembered Sign-Ins' not in credential_information
    assert 'Provider-managed recovery' in hero
    assert 'Other sessions are revoked; secrets stay out of audit.' in hero


def test_administrative_reset_now_revokes_target_sessions_and_no_longer_claims_they_remain_active() -> None:
    routes = read('app/users/routes.py')
    reset_template = read('app/templates/users/reset_password.html')
    readme = read('app/users/README.md')

    assert 'user.set_password(' in routes
    assert 'existing sessions were revoked' in routes
    assert 'Revoked on Next Request' in reset_template
    assert 'Remain Active' not in reset_template
    assert 'does not yet invalidate existing authenticated sessions' not in reset_template
    assert 'User.auth_session_version' in readme
