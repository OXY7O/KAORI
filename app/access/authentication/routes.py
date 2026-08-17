from datetime import UTC, datetime
from typing import cast

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, logout_user
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication.admission import enforce_login_admission
from app.access.authentication.audit import record_authentication_activity
from app.access.authentication.forms import LoginForm
from app.access.authentication.identity_provider.browser import (
    SsoProviderError,
    generate_nonce,
    generate_state,
    sso_flow_is_valid,
    state_fingerprint,
)
from app.access.authentication.identity_provider.catalog import provider_definition
from app.access.authentication.identity_provider.registry import get_browser_sso_adapter
from app.access.authentication.readiness import check_authentication_database_readiness
from app.access.authentication.results import ACCESS_NOT_PERMITTED_MESSAGE, AuthResult
from app.access.authentication.services import (
    DATABASE_UNAVAILABLE_MESSAGE,
    PROVIDER_UNAVAILABLE_MESSAGE,
    authenticate,
    credential_failure_message,
)
from app.access.authentication.session import (
    AuthSessionError,
    clear_authenticated_session,
    establish_authenticated_session,
    safe_next_url,
)
from app.access.authentication.sso import (
    SsoProviderStoreError,
    enabled_sso_providers,
    find_enabled_sso_provider,
    resolve_sso_identity,
)
from app.extensions.db import db
from app.extensions.limiter import limiter
from app.models import User
from app.platform_operations.notifications.service import queue_transient_feedback

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

SSO_SESSION_KEY = 'kaori_sso_flow'


def _client_ip() -> str | None:
    return request.remote_addr


def _record_result(username: str, result: AuthResult) -> None:
    record_authentication_activity(
        action='login',
        username=username,
        source=result.source,
        result='success' if result.success else 'failed',
        reason=result.reason,
        user=result.user,
    )


def _complete_successful_login(
    result: AuthResult,
    *,
    remember_requested: bool = False,
    next_url: object = None,
):
    user = result.user
    if user is None:
        raise RuntimeError('Successful authentication result is missing its user.')
    user.last_login_at = datetime.now(UTC)
    user.last_login_ip = _client_ip()
    user.last_auth_source = result.source
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise

    establish_authenticated_session(
        user,
        source=result.source,
        remember_requested=remember_requested,
    )
    return redirect(safe_next_url(next_url) or url_for('welcome.index'))


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit(
    lambda: current_app.config.get('AUTH_LOGIN_RATE_LIMIT', '5 per minute'),
    methods=['POST'],
)
def login():
    readiness = check_authentication_database_readiness()
    if not readiness.ready:
        # The setup page explains the database state directly.  Remove stale
        # authentication flashes so a fresh-database condition never appears
        # as several unrelated login failures.
        session.pop('_flashes', None)
        return (
            render_template(
                'access/authentication/setup_required.html',
                readiness=readiness,
            ),
            503,
        )

    if current_user.is_authenticated:
        return redirect(safe_next_url(request.args.get('next')) or url_for('welcome.index'))

    form = LoginForm()
    if request.method == 'GET':
        form.next.data = safe_next_url(request.args.get('next')) or ''
    if form.validate_on_submit():
        username = form.username.data or ''
        password = form.password.data or ''
        result = authenticate(username, password)

        if result.success and result.user:
            try:
                response = _complete_successful_login(
                    result,
                    remember_requested=bool(form.remember.data),
                    next_url=form.next.data,
                )
            except SQLAlchemyError:
                result = AuthResult(
                    False,
                    'database_unavailable',
                    source=result.source,
                    user=result.user,
                    message=DATABASE_UNAVAILABLE_MESSAGE,
                )
            except AuthSessionError:
                result = AuthResult(
                    False,
                    'access_not_permitted',
                    source=result.source,
                    user=result.user,
                    message=ACCESS_NOT_PERMITTED_MESSAGE,
                )
            else:
                _record_result(username, result)
                return response

        _record_result(username, result)
        message = credential_failure_message(result)
        queue_transient_feedback(
            status='error',
            title='Sign-in failed',
            message=message,
        )

    sso_provider_rows = [
        {'record': provider, 'definition': provider_definition(provider.provider_key)}
        for provider in enabled_sso_providers()
    ]
    return render_template('access/authentication/index.html', form=form, sso_provider_rows=sso_provider_rows)


@auth_bp.get('/sso/<provider_key>/start')
@limiter.limit(lambda: current_app.config.get('AUTH_SSO_RATE_LIMIT', '20 per minute'))
def sso_start(provider_key: str):
    if current_user.is_authenticated:
        return redirect(safe_next_url(request.args.get('next')) or url_for('welcome.index'))

    try:
        provider = find_enabled_sso_provider(provider_key)
    except SsoProviderStoreError:
        queue_transient_feedback(
            status='error',
            title='Authentication unavailable',
            message=DATABASE_UNAVAILABLE_MESSAGE,
        )
        return redirect(url_for('auth.login'))
    if provider is None:
        record_authentication_activity(
            action='login',
            username=provider_key,
            source='sso',
            result='failed',
            reason='provider_unavailable',
        )
        queue_transient_feedback(
            status='error',
            title='SSO provider unavailable',
            message='The selected SSO provider is unavailable.',
        )
        return redirect(url_for('auth.login'))

    state = generate_state()
    try:
        adapter = get_browser_sso_adapter(provider.adapter_key)
    except SsoProviderError:
        record_authentication_activity(
            action='login',
            username=provider.key,
            source=provider.provider_key,
            result='failed',
            reason='provider_unavailable',
        )
        queue_transient_feedback(
            status='error',
            title='SSO provider unavailable',
            message='The selected SSO provider is unavailable.',
        )
        return redirect(url_for('auth.login'))

    nonce = generate_nonce() if adapter.requires_nonce else None
    redirect_uri = url_for('auth.sso_callback', provider_key=provider.key, _external=True)
    session[SSO_SESSION_KEY] = {
        'provider_id': provider.id,
        'state_hash': state_fingerprint(state),
        'nonce': nonce,
        'started_at': datetime.now(UTC).timestamp(),
        'next_url': safe_next_url(request.args.get('next')),
    }
    try:
        authorization_url = adapter.build_authorization_url(
            provider,
            redirect_uri=redirect_uri,
            state=state,
            nonce=nonce,
        )
    except SsoProviderError as exc:
        session.pop(SSO_SESSION_KEY, None)
        current_app.logger.warning('SSO start failed for provider %s: %s', provider.key, exc)
        record_authentication_activity(
            action='login',
            username=provider.key,
            source=provider.provider_key,
            result='failed',
            reason='provider_unavailable',
        )
        queue_transient_feedback(
            status='error',
            title='SSO configuration failed',
            message='The selected SSO provider is not configured correctly.',
        )
        return redirect(url_for('auth.login'))
    return redirect(authorization_url)


@auth_bp.get('/sso/<provider_key>/callback')
@limiter.limit(lambda: current_app.config.get('AUTH_SSO_RATE_LIMIT', '20 per minute'))
def sso_callback(provider_key: str):
    raw_flow = session.pop(SSO_SESSION_KEY, None)
    flow = raw_flow if isinstance(raw_flow, dict) else {}
    try:
        provider = find_enabled_sso_provider(provider_key)
    except SsoProviderStoreError:
        queue_transient_feedback(
            status='error',
            title='Authentication unavailable',
            message=DATABASE_UNAVAILABLE_MESSAGE,
        )
        return redirect(url_for('auth.login'))
    if provider is None:
        record_authentication_activity(
            action='login',
            username=provider_key,
            source='sso',
            result='failed',
            reason='provider_unavailable',
        )
        queue_transient_feedback(
            status='error',
            title='SSO provider unavailable',
            message='The selected SSO provider is unavailable.',
        )
        return redirect(url_for('auth.login'))
    try:
        adapter = get_browser_sso_adapter(provider.adapter_key)
    except SsoProviderError:
        record_authentication_activity(
            action='login',
            username=provider.key,
            source=provider.provider_key,
            result='failed',
            reason='provider_unavailable',
        )
        queue_transient_feedback(
            status='error',
            title='SSO provider unavailable',
            message='The selected SSO provider is unavailable.',
        )
        return redirect(url_for('auth.login'))

    supplied_state = request.args.get('state', '')
    flow_ttl_seconds = int(current_app.config.get('AUTH_SSO_FLOW_TTL_SECONDS', 600))
    if not sso_flow_is_valid(
        flow,
        provider_id=provider.id,
        supplied_state=supplied_state,
        now_timestamp=datetime.now(UTC).timestamp(),
        ttl_seconds=flow_ttl_seconds,
    ):
        result = AuthResult(False, 'state_mismatch', source=provider.provider_key)
        _record_result(provider.key, result)
        queue_transient_feedback(
            status='error',
            title='SSO request expired',
            message='The SSO request expired or failed state validation. Start sign-in again.',
        )
        return redirect(url_for('auth.login'))

    provider_error = request.args.get('error')
    if provider_error:
        result = AuthResult(False, 'authorization_denied', source=provider.provider_key)
        _record_result(provider.key, result)
        queue_transient_feedback(
            status='warning',
            title='SSO sign-in cancelled',
            message='The external sign-in request was cancelled or denied.',
        )
        return redirect(url_for('auth.login'))

    code = request.args.get('code', '')
    if not code:
        result = AuthResult(False, 'authorization_code_missing', source=provider.provider_key)
        _record_result(provider.key, result)
        queue_transient_feedback(
            status='error',
            title='SSO callback incomplete',
            message='The SSO callback did not include an authorization code.',
        )
        return redirect(url_for('auth.login'))

    redirect_uri = url_for('auth.sso_callback', provider_key=provider.key, _external=True)
    try:
        identity = adapter.exchange_code(
            provider,
            code=code,
            redirect_uri=redirect_uri,
            expected_nonce=flow.get('nonce'),
        )
        result = enforce_login_admission(resolve_sso_identity(provider, identity))
    except SsoProviderError:
        current_app.logger.warning('SSO callback failed for provider %s.', provider.key, exc_info=True)
        result = AuthResult(False, 'provider_unavailable', source=provider.provider_key)

    audit_username = identity.username if 'identity' in locals() else provider.key
    if result.success and result.user:
        try:
            response = _complete_successful_login(result, next_url=flow.get('next_url'))
        except SQLAlchemyError:
            result = AuthResult(
                False,
                'database_unavailable',
                source=result.source,
                user=result.user,
                message=DATABASE_UNAVAILABLE_MESSAGE,
            )
        except AuthSessionError:
            result = AuthResult(
                False,
                'access_not_permitted',
                source=result.source,
                user=result.user,
                message=ACCESS_NOT_PERMITTED_MESSAGE,
            )
        else:
            _record_result(audit_username, result)
            return response

    _record_result(audit_username, result)
    queue_transient_feedback(
        status='error',
        title='SSO sign-in failed',
        message=result.message or PROVIDER_UNAVAILABLE_MESSAGE,
    )
    return redirect(url_for('auth.login'))


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    user = cast(User, current_user._get_current_object())
    source = str(session.get('auth_source') or user.last_auth_source or user.auth_source or 'database')
    record_authentication_activity(
        action='logout',
        username=user.username,
        source=source,
        result='success',
        reason='user_initiated',
        user=user,
    )
    logout_user()
    clear_authenticated_session()
    session.pop(SSO_SESSION_KEY, None)
    return redirect(url_for('auth.login'))
