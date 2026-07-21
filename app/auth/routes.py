from datetime import UTC, datetime
from secrets import compare_digest
from typing import cast

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, logout_user

from app.auth.audit import record_authentication_activity
from app.auth.forms import LoginForm
from app.auth.providers.oauth import (
    SsoProviderError,
    build_authorization_url,
    exchange_code,
    generate_nonce,
    generate_state,
    state_fingerprint,
)
from app.auth.readiness import check_authentication_database_readiness
from app.auth.results import AuthResult
from app.auth.services import (
    DATABASE_UNAVAILABLE_MESSAGE,
    INVALID_LOGIN_MESSAGE,
    PROVIDER_UNAVAILABLE_MESSAGE,
    authenticate,
)
from app.auth.session import clear_authenticated_session, establish_authenticated_session
from app.auth.sso import enabled_sso_providers, resolve_sso_identity
from app.extensions import db, limiter
from app.models import IdentityProvider, User

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


def _complete_successful_login(result: AuthResult, *, remember_requested: bool = False):
    user = result.user
    if user is None:
        raise RuntimeError('Successful authentication result is missing its user.')
    user.last_login_at = datetime.now(UTC)
    user.last_login_ip = _client_ip()
    user.last_auth_source = result.source
    db.session.commit()

    establish_authenticated_session(
        user,
        source=result.source,
        remember_requested=remember_requested,
    )
    return redirect(url_for('welcome.index'))


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
                'auth/setup_required.html',
                readiness=readiness,
            ),
            503,
        )

    if current_user.is_authenticated:
        return redirect(url_for('welcome.index'))

    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data or ''
        password = form.password.data or ''
        result = authenticate(username, password)
        _record_result(username, result)

        if result.success and result.user:
            return _complete_successful_login(result, remember_requested=bool(form.remember.data))

        if result.reason == 'database_unavailable':
            message = result.message or DATABASE_UNAVAILABLE_MESSAGE
        elif result.reason == 'provider_unavailable':
            message = result.message or PROVIDER_UNAVAILABLE_MESSAGE
        else:
            message = result.message or INVALID_LOGIN_MESSAGE
        flash(message, 'danger')

    return render_template('auth/index.html', form=form, sso_providers=enabled_sso_providers())


@auth_bp.get('/sso/<provider_key>/start')
@limiter.limit(lambda: current_app.config.get('AUTH_SSO_RATE_LIMIT', '20 per minute'))
def sso_start(provider_key: str):
    if current_user.is_authenticated:
        return redirect(url_for('welcome.index'))

    provider = IdentityProvider.query.filter_by(key=provider_key, enabled=True).first()
    if provider is None or not provider.is_sso:
        flash('The selected SSO provider is unavailable.', 'danger')
        return redirect(url_for('auth.login'))

    state = generate_state()
    nonce = generate_nonce() if provider.provider_type == 'google_oidc' else None
    redirect_uri = url_for('auth.sso_callback', provider_key=provider.key, _external=True)
    session[SSO_SESSION_KEY] = {
        'provider_id': provider.id,
        'state_hash': state_fingerprint(state),
        'nonce': nonce,
        'started_at': datetime.now(UTC).timestamp(),
    }
    try:
        authorization_url = build_authorization_url(
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
            source=provider.provider_type,
            result='failed',
            reason='provider_unavailable',
        )
        flash('The selected SSO provider is not configured correctly.', 'danger')
        return redirect(url_for('auth.login'))
    return redirect(authorization_url)


@auth_bp.get('/sso/<provider_key>/callback')
@limiter.limit(lambda: current_app.config.get('AUTH_SSO_RATE_LIMIT', '20 per minute'))
def sso_callback(provider_key: str):
    flow = session.pop(SSO_SESSION_KEY, None) or {}
    provider = IdentityProvider.query.filter_by(key=provider_key, enabled=True).first()
    if provider is None or not provider.is_sso:
        flash('The selected SSO provider is unavailable.', 'danger')
        return redirect(url_for('auth.login'))

    supplied_state = request.args.get('state', '')
    expected_hash = str(flow.get('state_hash') or '')
    provider_matches = int(flow.get('provider_id') or 0) == provider.id
    state_matches = bool(supplied_state and expected_hash) and compare_digest(
        state_fingerprint(supplied_state), expected_hash
    )
    started_at = float(flow.get('started_at') or 0)
    not_expired = started_at > 0 and (datetime.now(UTC).timestamp() - started_at) <= 600
    if not (provider_matches and state_matches and not_expired):
        result = AuthResult(False, 'state_mismatch', source=provider.provider_type)
        _record_result(provider.key, result)
        flash('The SSO request expired or failed state validation. Start sign-in again.', 'danger')
        return redirect(url_for('auth.login'))

    provider_error = request.args.get('error')
    if provider_error:
        result = AuthResult(False, 'authorization_denied', source=provider.provider_type)
        _record_result(provider.key, result)
        flash('The external sign-in request was cancelled or denied.', 'danger')
        return redirect(url_for('auth.login'))

    code = request.args.get('code', '')
    if not code:
        result = AuthResult(False, 'authorization_code_missing', source=provider.provider_type)
        _record_result(provider.key, result)
        flash('The SSO callback did not include an authorization code.', 'danger')
        return redirect(url_for('auth.login'))

    redirect_uri = url_for('auth.sso_callback', provider_key=provider.key, _external=True)
    try:
        identity = exchange_code(
            provider,
            code=code,
            redirect_uri=redirect_uri,
            expected_nonce=flow.get('nonce'),
        )
        result = resolve_sso_identity(provider, identity)
    except SsoProviderError:
        current_app.logger.warning('SSO callback failed for provider %s.', provider.key, exc_info=True)
        result = AuthResult(False, 'provider_unavailable', source=provider.provider_type)

    _record_result(identity.username if 'identity' in locals() else provider.key, result)
    if result.success and result.user:
        return _complete_successful_login(result)

    flash(result.message or PROVIDER_UNAVAILABLE_MESSAGE, 'danger')
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
