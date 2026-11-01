"""Focused read-only Settings authorization and password rejection regressions.

Negative cases never commit credentials or call external identity providers.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask, jsonify, request
from flask_login import LoginManager, UserMixin
from flask_wtf.csrf import generate_csrf

from app.platform_operations.notifications.feedback import OperationalDeliveryPolicy
from app.settings.account.actions import process_password_change
from app.settings.general.actions import (
    save_regional_format_preference,
    save_timezone_preference,
    sync_browser_timezone_preference,
)
from app.settings.general.forms import RegionalFormatForm, TimezonePreferenceForm
from app.settings.routes import bp, general, sync_browser_timezone
from app.settings.system_information import build_system_information


def _settings_app() -> Flask:
    app = Flask(__name__)
    app.config.update(SECRET_KEY='settings-contract-only', WTF_CSRF_ENABLED=False)
    app.register_blueprint(bp)
    return app


@pytest.mark.parametrize('requested', ('system-information', 'compatibility-versions'))
def test_general_rejects_privileged_reference_tabs_without_system_view(
    requested: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _settings_app()
    user = SimpleNamespace(
        timezone_mode='manual',
        timezone='UTC',
        locale='en-US',
        date_format='day_month_year',
        time_format='24h',
        has_permission=Mock(return_value=False),
    )

    # Avoid unittest.mock inspecting Flask-Login's LocalProxy before its manager is initialized.
    monkeypatch.setattr(
        'app.settings.routes.current_user',
        SimpleNamespace(_get_current_object=lambda: user),
    )

    with (
        app.test_request_context(f'/settings/general?tab={requested}'),
        patch('app.settings.routes.render_template', return_value='isolated settings') as render,
        patch('app.settings.routes.build_system_information') as system_information,
        patch('app.settings.routes.format_user_datetime', return_value='isolated clock'),
    ):
        response = general.__wrapped__()  # Exercise the actual route logic without Flask-Login.
        assert response.status_code == 200
        assert b'isolated settings' in response.get_data()
        assert render.call_args.kwargs['active_tab'] == 'time-locale'
        assert render.call_args.kwargs['can_view_system_information'] is False
        assert render.call_args.kwargs['compatibility_registry'] is None
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
    password_matches: tuple[bool, ...],
    expected_reason: str,
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


@pytest.mark.parametrize(
    ('timezone_mode', 'requested_timezone', 'detected_timezone'),
    [
        ('manual', 'Not/A-Timezone', 'Asia/Jakarta'),
        ('automatic', 'Asia/Jakarta', 'Not/A-Timezone'),
    ],
)
def test_invalid_iana_timezone_submissions_preserve_saved_account_preference(
    timezone_mode: str, requested_timezone: str, detected_timezone: str
) -> None:
    """Reject forged manual select and automatic browser values without mutation."""
    app = _settings_app()
    user = SimpleNamespace(
        id=71,
        timezone_mode='manual',
        timezone='Asia/Jakarta',
    )
    data = {
        'timezone_mode': timezone_mode,
        'timezone': requested_timezone,
        'browser_timezone': detected_timezone,
        'submit_timezone': 'Save',
    }
    with (
        app.test_request_context('/settings/general?tab=time-locale', method='POST', data=data),
        patch('app.settings.general.actions.create_transient_feedback', return_value={'status': 'error'}),
        patch('app.settings.general.actions.db.session.commit') as commit,
        patch('app.settings.general.actions.record_operational_activity') as audit,
    ):
        form = TimezonePreferenceForm()
        result = save_timezone_preference(user=user, form=form, is_htmx=True)

    assert result.saved is False
    assert result.feedback == {'status': 'error'}
    assert user.timezone_mode == 'manual'
    assert user.timezone == 'Asia/Jakarta'
    assert form.errors or form.timezone.errors
    commit.assert_not_called()
    audit.assert_not_called()


@pytest.mark.parametrize('tab', ('time-locale', 'regional-format'))
def test_general_preference_forms_reject_missing_csrf_before_any_mutation(tab: str) -> None:
    """Exercise Flask-WTF's real missing-token validation for either Settings POST."""
    app = _settings_app()
    app.config['WTF_CSRF_ENABLED'] = True
    user = SimpleNamespace(
        id=72,
        timezone_mode='manual',
        timezone='Asia/Jakarta',
        locale='en-US',
        date_format='day_month_year',
        time_format='24h',
    )
    data = (
        {
            'timezone_mode': 'manual',
            'timezone': 'Asia/Makassar',
            'browser_timezone': 'Asia/Makassar',
            'submit_timezone': 'Save',
        }
        if tab == 'time-locale'
        else {
            'locale': 'id-ID',
            'date_format': 'year_month_day',
            'time_format': '12h',
            'submit_regional': 'Save',
        }
    )

    with (
        app.test_request_context(f'/settings/general?tab={tab}', method='POST', data=data),
        patch('app.settings.general.actions.create_transient_feedback', return_value={'status': 'error'}),
        patch('app.settings.general.actions.db.session.commit') as commit,
        patch('app.settings.general.actions.record_operational_activity') as audit,
    ):
        if tab == 'time-locale':
            form = TimezonePreferenceForm()
            result = save_timezone_preference(user=user, form=form, is_htmx=True)
        else:
            form = RegionalFormatForm()
            result = save_regional_format_preference(user=user, form=form, is_htmx=True)

    assert result.saved is False
    assert form.csrf_token.errors
    assert user.timezone_mode == 'manual'
    assert user.timezone == 'Asia/Jakarta'
    assert (user.locale, user.date_format, user.time_format) == ('en-US', 'day_month_year', '24h')
    commit.assert_not_called()
    audit.assert_not_called()


@pytest.mark.parametrize(
    ('saved_mode', 'detected', 'expected_status'),
    [
        ('manual', 'Asia/Makassar', 'ignored'),
        ('automatic', 'Not/A-Timezone', 'invalid_timezone'),
        ('automatic', 'Asia/Jakarta', 'unchanged'),
    ],
)
def test_browser_timezone_sync_denies_untrusted_or_unchanged_updates(
    saved_mode: str, detected: str, expected_status: str
) -> None:
    """Do not persist browser-timezone input outside a valid automatic update."""
    app = _settings_app()
    user = SimpleNamespace(timezone_mode=saved_mode, timezone='Asia/Jakarta')
    with (
        app.test_request_context('/settings/general/browser-timezone', method='POST'),
        patch('app.settings.general.actions.db.session.commit') as commit,
    ):
        status, timezone = sync_browser_timezone_preference(user=user, browser_timezone=detected)
    assert status == expected_status
    assert timezone == 'Asia/Jakarta'
    assert user.timezone == 'Asia/Jakarta'
    commit.assert_not_called()


@pytest.mark.parametrize('csrf_value', (None, 'forged-token'))
def test_browser_timezone_json_post_rejects_missing_or_invalid_csrf(csrf_value: str | None) -> None:
    """The standalone JSON mutation must not bypass Flask-WTF's session token."""
    app = _settings_app()
    app.config['WTF_CSRF_ENABLED'] = True
    user = SimpleNamespace(timezone_mode='automatic', timezone='Asia/Jakarta')
    headers = {'X-CSRFToken': csrf_value} if csrf_value is not None else {}

    with (
        app.test_request_context(
            '/settings/general/browser-timezone',
            method='POST',
            json={'timezone': 'Asia/Makassar'},
            headers=headers,
        ),
        patch(
            'app.settings.routes.current_user',
            SimpleNamespace(_get_current_object=lambda: user),
        ),
        patch('app.settings.routes.sync_browser_timezone_preference') as sync,
        patch('app.settings.general.actions.db.session.commit') as commit,
    ):
        # A valid server-side CSRF session exists; the header is still absent or forged.
        generate_csrf()
        response, status = sync_browser_timezone.__wrapped__()

    assert status == 400
    assert response.get_json() == {'status': 'invalid_csrf'}
    assert user.timezone == 'Asia/Jakarta'
    sync.assert_not_called()
    commit.assert_not_called()


def test_browser_timezone_json_post_accepts_valid_session_csrf() -> None:
    """Preserve the legitimate same-origin auto-sync path with a bound token."""
    app = _settings_app()
    app.config['WTF_CSRF_ENABLED'] = True
    user = SimpleNamespace(timezone_mode='automatic', timezone='Asia/Jakarta')

    with (
        app.test_request_context(
            '/settings/general/browser-timezone',
            method='POST',
            json={'timezone': 'Asia/Makassar'},
            headers={'X-CSRFToken': 'pending-session-token'},
        ),
        patch(
            'app.settings.routes.current_user',
            SimpleNamespace(_get_current_object=lambda: user),
        ),
        patch('app.settings.general.actions.db.session.commit') as commit,
    ):
        # Generate the real Flask-WTF token in the same request/session.
        request.environ['HTTP_X_CSRFTOKEN'] = generate_csrf()
        response, status = sync_browser_timezone.__wrapped__()

    assert status == 200
    assert response.get_json() == {'status': 'updated', 'timezone': 'Asia/Makassar'}
    assert user.timezone == 'Asia/Makassar'
    commit.assert_called_once()


def test_browser_timezone_json_client_uses_session_bound_csrf_header() -> None:
    """The existing browser script must retain the server-approved header."""
    root = Path(__file__).resolve().parents[3]
    client = (root / 'app/static/js/user_timezone_sync.js').read_text(encoding='utf-8')
    layout = (root / 'app/templates/layouts/app.html').read_text(encoding='utf-8')
    assert "'X-CSRFToken': csrfToken" in client
    assert "credentials: 'same-origin'" in client
    assert 'data-csrf="{{ csrf_token() }}"' in layout


class _SettingsCsrfHttpUser(UserMixin):
    """Synthetic identity used only by the isolated JSON HTTP boundary tests."""

    id = 'csrf-contract-user'


@pytest.mark.parametrize(
    ('token_kind', 'expected_status', 'expected_result'),
    [
        ('missing', 400, 'invalid_csrf'),
        ('forged', 400, 'invalid_csrf'),
        ('other_session', 400, 'invalid_csrf'),
        ('valid', 200, 'updated'),
    ],
)
def test_browser_timezone_json_http_csrf_boundary(token_kind: str, expected_status: int, expected_result: str) -> None:
    """Exercise real Flask routing/login/session/CSRF before mutating test state."""
    app = _settings_app()
    app.config['WTF_CSRF_ENABLED'] = True
    manager = LoginManager()
    manager.init_app(app)
    identity = _SettingsCsrfHttpUser()
    manager.user_loader(lambda identifier: identity if identifier == identity.get_id() else None)

    @app.get('/_settings_contract/csrf')
    def _test_csrf_token():
        return jsonify({'csrf_token': generate_csrf()})

    # Generate the foreign token before opening the primary test client.
    # Nested preserved test-client contexts may reuse Flask's app-context g
    # CSRF cache, incorrectly turning a foreign-session negative into HTTP 200.
    foreign_token = None
    if token_kind == 'other_session':
        with app.test_client() as other_client:
            foreign_response = other_client.get('/_settings_contract/csrf')
            assert foreign_response.status_code == 200
            foreign_token = foreign_response.get_json()['csrf_token']

    user = SimpleNamespace(id=71, timezone_mode='automatic', timezone='Asia/Jakarta')
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['_user_id'] = identity.get_id()
            session['_fresh'] = True
        csrf_response = client.get('/_settings_contract/csrf')
        assert csrf_response.status_code == 200
        valid_token = csrf_response.get_json()['csrf_token']

        headers = {}
        if token_kind == 'forged':
            headers['X-CSRFToken'] = 'forged-token'
        elif token_kind == 'other_session':
            assert foreign_token is not None and foreign_token != valid_token
            headers['X-CSRFToken'] = foreign_token
        elif token_kind == 'valid':
            headers['X-CSRFToken'] = valid_token

        with (
            patch(
                'app.settings.routes.current_user',
                SimpleNamespace(_get_current_object=lambda: user),
            ),
            patch('app.settings.general.actions.db.session.commit') as commit,
        ):
            response = client.post(
                '/settings/general/browser-timezone',
                json={'timezone': 'Asia/Makassar'},
                headers=headers,
            )

    assert response.status_code == expected_status
    payload = response.get_json()
    assert payload['status'] == expected_result
    if token_kind == 'valid':
        assert payload['timezone'] == 'Asia/Makassar'
        assert user.timezone == 'Asia/Makassar'
        commit.assert_called_once()
    else:
        assert user.timezone == 'Asia/Jakarta'
        assert set(payload) == {'status'}
        commit.assert_not_called()


def test_browser_timezone_json_http_requires_authenticated_session() -> None:
    """Unauthenticated HTTP requests cannot reach the preference mutation."""
    app = _settings_app()
    app.config['WTF_CSRF_ENABLED'] = True
    manager = LoginManager()
    manager.init_app(app)
    manager.user_loader(lambda _identifier: None)
    user = SimpleNamespace(id=71, timezone_mode='automatic', timezone='Asia/Jakarta')

    with (
        app.test_client() as client,
        patch(
            'app.settings.routes.current_user',
            SimpleNamespace(_get_current_object=lambda: user),
        ),
        patch('app.settings.general.actions.db.session.commit') as commit,
    ):
        response = client.post(
            '/settings/general/browser-timezone',
            json={'timezone': 'Asia/Makassar'},
        )

    assert response.status_code in {302, 401}
    assert user.timezone == 'Asia/Jakarta'
    commit.assert_not_called()
