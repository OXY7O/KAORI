from datetime import UTC, datetime
from typing import cast

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, logout_user
from flask_wtf.csrf import validate_csrf
from sqlalchemy.exc import SQLAlchemyError
from wtforms.validators import ValidationError

from app.access.authentication.admission import enforce_login_admission
from app.access.authentication.audit import record_authentication_activity
from app.access.authentication.bot_protection.service import (
    BotConfigurationError,
    bot_policy_state,
    bot_token_verified,
)
from app.access.authentication.forms import LoginForm, MfaChallengeForm
from app.access.authentication.identity_provider.browser import (
    SsoProviderError,
    generate_nonce,
    generate_state,
    sso_flow_is_valid,
    state_fingerprint,
)
from app.access.authentication.identity_provider.catalog import provider_definition
from app.access.authentication.identity_provider.registry import get_browser_sso_adapter
from app.access.authentication.mfa.policy import MfaGate
from app.access.authentication.mfa.service import (
    MFA_CHALLENGE_TTL_SECONDS,
    MfaVerificationError,
    begin_mfa_enrollment,
    confirm_mfa_enrollment,
    mfa_decision,
    verify_mfa_challenge,
)
from app.access.authentication.readiness import check_authentication_database_readiness
from app.access.authentication.results import ACCESS_NOT_PERMITTED_MESSAGE, AuthResult
from app.access.authentication.services import (
    DATABASE_UNAVAILABLE_MESSAGE,
    PROVIDER_UNAVAILABLE_MESSAGE,
    authenticate,
    credential_failure_message,
    record_successful_authentication,
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
from app.extensions.limiter import limiter
from app.models import User
from app.platform_operations.notifications.service import queue_transient_feedback

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

SSO_SESSION_KEY = 'kaori_sso_flow'
SSO_BOT_GRANT_KEY = 'kaori_sso_bot_grant'
SSO_BOT_GRANT_TTL_SECONDS = 60
MFA_PENDING_SESSION_KEY = 'kaori_mfa_pending'


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
    mfa_verified: bool = False,
):
    user = result.user
    if user is None:
        raise RuntimeError('Successful authentication result is missing its user.')

    # A primary-credential-only result may NOT invalidate the previous login.
    # Every required factor must be verified before generation issuance (#3121).
    if not mfa_verified:
        decision = mfa_decision(user)
        if decision.gate in (MfaGate.CHALLENGE, MfaGate.ENROLLMENT_REQUIRED):
            session.clear()
            session[MFA_PENDING_SESSION_KEY] = {
                'user_id': user.id,
                'source': result.source,
                'version': user.auth_session_version,
                'remember': bool(remember_requested),
                'next_url': safe_next_url(next_url),
                'expires_at': datetime.now(UTC).timestamp() + MFA_CHALLENGE_TTL_SECONDS,
                'attempts': 0,
            }
            return redirect(url_for('auth.mfa_challenge'))
    issued_session_version = record_successful_authentication(user, source=result.source, client_ip=_client_ip())

    establish_authenticated_session(
        user,
        source=result.source,
        remember_requested=remember_requested,
        issued_session_version=issued_session_version,
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

    try:
        bot_state = bot_policy_state()
    except BotConfigurationError:
        return 'Authentication protection is temporarily unavailable.', 503

    form = LoginForm()
    if request.method == 'GET':
        form.next.data = safe_next_url(request.args.get('next')) or ''
    if form.validate_on_submit():
        if not bot_token_verified(request.form.get('cf-turnstile-response'), bot_state):
            record_authentication_activity(
                action='login',
                username=str(form.username.data or ''),
                source='credentials',
                result='failed',
                reason='bot_challenge_failed',
            )
            queue_transient_feedback(
                status='error',
                title='Sign-in verification failed',
                message='Complete the security challenge and try again.',
            )
            return redirect(url_for('auth.login'))
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
                # Do not write a successful sign-in event for primary-auth-only
                # pending challenges. Audit success only after factor completion.
                if MFA_PENDING_SESSION_KEY not in session:
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
    return render_template(
        'access/authentication/index.html',
        form=form,
        sso_provider_rows=sso_provider_rows,
        bot_state=bot_state,
    )


@auth_bp.route('/sso/<provider_key>/bot', methods=['GET', 'POST'])
@limiter.limit('5 per minute', methods=['POST'])
def sso_bot_challenge(provider_key: str):
    """Require a fresh server-verified challenge before entering external SSO."""
    if current_user.is_authenticated:
        return redirect(url_for('welcome.index'))
    try:
        bot_state = bot_policy_state()
    except BotConfigurationError:
        return 'Authentication protection is temporarily unavailable.', 503
    next_url = safe_next_url(request.values.get('next'))
    if not bot_state.enabled:
        return redirect(url_for('auth.sso_start', provider_key=provider_key, next=next_url))
    error = None
    if request.method == 'POST':
        try:
            validate_csrf(request.form.get('csrf_token'))
        except ValidationError:
            return 'Invalid request.', 400
        if bot_token_verified(request.form.get('cf-turnstile-response'), bot_state):
            session[SSO_BOT_GRANT_KEY] = {
                'provider_key': provider_key,
                'next_url': next_url,
                'verified_at': datetime.now(UTC).timestamp(),
            }
            return redirect(url_for('auth.sso_start', provider_key=provider_key, next=next_url))
        error = 'Complete the security challenge and try again.'
        record_authentication_activity(
            action='login',
            username=provider_key,
            source='sso',
            result='failed',
            reason='bot_challenge_failed',
        )
    return render_template(
        'access/authentication/bot_challenge.html',
        bot_state=bot_state,
        provider_key=provider_key,
        next_url=next_url,
        error=error,
    )


@auth_bp.get('/sso/<provider_key>/start')
@limiter.limit(lambda: current_app.config.get('AUTH_SSO_RATE_LIMIT', '20 per minute'))
def sso_start(provider_key: str):
    if current_user.is_authenticated:
        return redirect(safe_next_url(request.args.get('next')) or url_for('welcome.index'))
    try:
        bot_state = bot_policy_state()
    except BotConfigurationError:
        return 'Authentication protection is temporarily unavailable.', 503
    bot_verified_at = None
    if bot_state.enabled:
        grant = session.pop(SSO_BOT_GRANT_KEY, None)
        now = datetime.now(UTC).timestamp()
        next_url = safe_next_url(request.args.get('next'))
        if (
            not isinstance(grant, dict)
            or grant.get('provider_key') != provider_key
            or grant.get('next_url') != next_url
            or type(grant.get('verified_at')) not in (int, float)
            or not 0 <= now - grant['verified_at'] <= SSO_BOT_GRANT_TTL_SECONDS
        ):
            return redirect(url_for('auth.sso_bot_challenge', provider_key=provider_key, next=next_url))
        bot_verified_at = grant['verified_at']

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
        'bot_verified_at': bot_verified_at,
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
    try:
        callback_bot_state = bot_policy_state()
    except BotConfigurationError:
        return 'Authentication protection is temporarily unavailable.', 503
    if callback_bot_state.enabled:
        checked_at = flow.get('bot_verified_at')
        age = datetime.now(UTC).timestamp() - checked_at if type(checked_at) in (int, float) else -1
        if age < 0 or age > flow_ttl_seconds:
            return redirect(url_for('auth.login'))

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
            if MFA_PENDING_SESSION_KEY not in session:
                _record_result(audit_username, result)
            return response

    _record_result(audit_username, result)
    queue_transient_feedback(
        status='error',
        title='SSO sign-in failed',
        message=result.message or PROVIDER_UNAVAILABLE_MESSAGE,
    )
    return redirect(url_for('auth.login'))


@auth_bp.route('/mfa', methods=['GET', 'POST'])
@limiter.limit('5 per minute', methods=['POST'])
def mfa_challenge():
    """Restricted second-factor challenge: no Flask-Login until proof succeeds."""
    raw = session.get(MFA_PENDING_SESSION_KEY)
    pending = raw if isinstance(raw, dict) else {}
    expires_at = pending.get('expires_at')
    if (
        type(pending.get('user_id')) is not int
        or type(expires_at) not in (int, float)
        or expires_at <= datetime.now(UTC).timestamp()
        or type(pending.get('attempts')) is not int
        or pending.get('attempts', 0) >= 5
    ):
        session.pop(MFA_PENDING_SESSION_KEY, None)
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(id=pending['user_id']).first()
    if (
        user is None
        or not user.is_active
        or str(user.auth_source) != str(pending.get('source'))
        or user.auth_session_version != pending.get('version')
    ):
        session.pop(MFA_PENDING_SESSION_KEY, None)
        return redirect(url_for('auth.login'))
    decision = mfa_decision(user)
    if decision.gate not in (MfaGate.CHALLENGE, MfaGate.ENROLLMENT_REQUIRED):
        session.pop(MFA_PENDING_SESSION_KEY, None)
        return redirect(url_for('auth.login'))

    form = MfaChallengeForm()
    if decision.gate == MfaGate.ENROLLMENT_REQUIRED:
        setup_secret = None
        codes = None
        enrollment_error = None
        if request.method == 'POST':
            pending['attempts'] += 1
            session[MFA_PENDING_SESSION_KEY] = pending
            action = str(request.form.get('mfa_action') or '')
            try:
                validate_csrf(request.form.get('csrf_token'))
                if action == 'begin':
                    setup_secret = begin_mfa_enrollment(user, authenticated=False)
                elif action == 'confirm' and form.validate_on_submit():
                    codes = confirm_mfa_enrollment(user, str(form.verification_code.data or ''), authenticated=False)
                else:
                    raise MfaVerificationError('Invalid enrollment request.')
            except (ValidationError, MfaVerificationError):
                enrollment_error = 'Enrollment could not be verified. Check your code or start again.'
            except SQLAlchemyError:
                enrollment_error = 'Authentication is temporarily unavailable.'
            if codes is not None:
                # Proof has become active. Revalidate the account and create
                # the ONLY authenticated session for this completed flow.
                result = enforce_login_admission(
                    AuthResult(True, 'success', source=str(pending['source']), user=user)
                )
                if not result.success:
                    session.pop(MFA_PENDING_SESSION_KEY, None)
                    return redirect(url_for('auth.login'))
                try:
                    _complete_successful_login(
                        result, remember_requested=bool(pending.get('remember')),
                        next_url=pending.get('next_url'), mfa_verified=True,
                    )
                except (SQLAlchemyError, AuthSessionError):
                    session.pop(MFA_PENDING_SESSION_KEY, None)
                    return redirect(url_for('auth.login'))
                _record_result(user.username, result)
                response = current_app.make_response(
                    render_template('access/authentication/mfa_recovery_codes.html', codes=codes)
                )
                response.headers['Cache-Control'] = 'no-store'
                return response
        return render_template(
            'access/authentication/mfa_enrollment.html',
            form=form, setup_secret=setup_secret, error=enrollment_error,
        )
    error = None
    if form.validate_on_submit():
        # Failed attempts are bounded in the signed pending-auth cookie as
        # well as the shared server-side request limiter.
        pending['attempts'] += 1
        session[MFA_PENDING_SESSION_KEY] = pending
        try:
            verify_mfa_challenge(user, str(form.verification_code.data or ''))
        except MfaVerificationError:
            error = 'The verification code was not accepted.'
            record_authentication_activity(
                action='login', username=user.username, source=str(pending['source']),
                result='failed', reason='mfa_challenge_failed', user=user,
            )
        except SQLAlchemyError:
            error = 'Authentication is temporarily unavailable.'
        else:
            # Recheck current source and account state after consuming one-time
            # proof. This is the only point that issues an authenticated cookie.
            result = enforce_login_admission(
                AuthResult(True, 'success', source=str(pending['source']), user=user)
            )
            if not result.success:
                session.pop(MFA_PENDING_SESSION_KEY, None)
                return redirect(url_for('auth.login'))
            try:
                response = _complete_successful_login(
                    result, remember_requested=bool(pending.get('remember')),
                    next_url=pending.get('next_url'), mfa_verified=True,
                )
            except (SQLAlchemyError, AuthSessionError):
                session.pop(MFA_PENDING_SESSION_KEY, None)
                return redirect(url_for('auth.login'))
            _record_result(user.username, result)
            return response

    return render_template('access/authentication/mfa_challenge.html', form=form, error=error)


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
