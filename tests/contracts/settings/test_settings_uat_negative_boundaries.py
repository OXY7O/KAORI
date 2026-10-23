"""Focused read-only Settings authorization and password rejection regressions.

Negative cases never commit credentials or call external identity providers.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from app.platform_operations.notifications.feedback import OperationalDeliveryPolicy
from app.settings.account.actions import process_password_change
from app.settings.routes import bp, general
from app.settings.system_information import build_system_information


def _settings_app() -> Flask:
    app = Flask(__name__)
    app.config.update(SECRET_KEY='settings-contract-only', WTF_CSRF_ENABLED=False)
    app.register_blueprint(bp)
    return app


@pytest.mark.parametrize('requested', ('system-information', 'compatibility-versions'))
def test_general_rejects_privileged_reference_tabs_without_system_view(requested: str) -> None:
    app = _settings_app()
    user = SimpleNamespace(
        timezone_mode='manual',
        timezone='UTC',
        locale='en-US',
        date_format='day_month_year',
        time_format='24h',
        has_permission=Mock(return_value=False),
    )

    with (
        app.test_request_context(f'/settings/general?tab={requested}'),
        patch('app.settings.routes.current_user') as current_user,
        patch('app.settings.routes.render_template', return_value='isolated settings'),
        patch('app.settings.routes.build_system_information') as system_information,
        patch('app.settings.routes.format_user_datetime', return_value='isolated clock'),
    ):
        current_user._get_current_object.return_value = user
        response = general.__wrapped__()  # Exercise the actual route logic without Flask-Login.
        assert response.status_code == 200
        assert b'isolated settings' in response.get_data()
        system_information.assert_not_called()
        user.has_permission.assert_called_with('system.view')


def test_system_information_never_projects_unrelated_sensitive_configuration() -> None:
    context = build_system_information(
        {
            'APP_NAME': 'KAORI',
            'APP_VERSION': 'uat-check',
            'APP_ENV': 'testing',
            'APP_BUILD_SHA': 'public-build-ref',
            'SECRET_KEY': 'sensitive-csrf-material',
            'SQLALCHEMY_DATABASE_URI': 'postgresql://private-database-host',
            'REDIS_URL': 'redis://private-cache-host',
            'AUTH_PROVIDER_CLIENT_SECRET': 'private-sso-credential',
        }
    )
    assert context['build_sha'] == 'public-build-ref'
    assert context['version'] == 'uat-check'
    projection = str(context)
    for secret in (
        'sensitive-csrf-material',
        'private-database-host',
        'private-cache-host',
        'private-sso-credential',
    ):
        assert secret not in projection


def _password_form() -> Mock:
    form = Mock()
    form.validate.return_value = True
    form.current_password.data = 'old-local-credential'
    form.current_password.errors = []
    form.new_password.data = 'new-local-credential'
    form.new_password.errors = []
    return form


@pytest.mark.parametrize('external_source', ('ldap', 'google', 'github'))
def test_external_credentials_are_rejected_before_validation_or_password_access(external_source: str) -> None:
    app = _settings_app()
    user = Mock()
    user.id = 22
    form = _password_form()
    with (
        app.test_request_context('/settings/account?tab=credentials'),
        patch('app.settings.account.actions.record_operational_activity', return_value={}) as audit,
        patch('app.settings.account.actions.db.session.commit') as commit,
    ):
        result = process_password_change(user=user, form=form, auth_source=external_source, is_htmx=True)

    assert result.saved is False
    assert result.inline_feedback is not None
    assert result.inline_feedback['title'] == 'Password is managed externally'
    form.validate.assert_not_called()
    user.check_password.assert_not_called()
    user.set_password.assert_not_called()
    commit.assert_not_called()
    assert audit.call_args.kwargs['metadata']['reason_code'] == 'external_credential_owner'
    assert audit.call_args.kwargs['delivery_policy'] is OperationalDeliveryPolicy.AUDIT_ONLY


@pytest.mark.parametrize(
    ('password_matches', 'expected_reason'),
    [
        ((False,), 'current_password_mismatch'),
        ((True, True), 'current_password_reuse'),
    ],
)
def test_password_rejections_preserve_credential_and_session_state(
    password_matches: tuple[bool, ...], expected_reason: str,
) -> None:
    app = _settings_app()
    user = Mock()
    user.id = 23
    user.check_password.side_effect = password_matches
    form = _password_form()
    with (
        app.test_request_context('/settings/account?tab=credentials'),
        patch('app.settings.account.actions.record_operational_activity', return_value={}) as audit,
        patch('app.settings.account.actions.db.session.commit') as commit,
        patch('app.settings.account.actions.preserve_current_session_after_password_change') as preserve,
    ):
        result = process_password_change(user=user, form=form, auth_source='database', is_htmx=True)

    assert result.saved is False
    assert result.inline_feedback is not None
    assert result.inline_feedback['status'] == 'danger'
    user.set_password.assert_not_called()
    commit.assert_not_called()
    preserve.assert_not_called()
    assert audit.call_args.kwargs['metadata']['reason_code'] == expected_reason
    assert audit.call_args.kwargs['delivery_policy'] is OperationalDeliveryPolicy.AUDIT_ONLY
