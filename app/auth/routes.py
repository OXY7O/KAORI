from datetime import UTC, datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, logout_user

from app.auth.audit import record_login_attempt
from app.auth.forms import LoginForm
from app.auth.results import AuthResult
from app.auth.services import DATABASE_UNAVAILABLE_MESSAGE, INVALID_LOGIN_MESSAGE, authenticate
from app.auth.session import clear_authenticated_session, establish_authenticated_session
from app.extensions import db, limiter

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def _client_ip() -> str | None:
    """Return the proxy-normalized client address.

    Production deployments apply Werkzeug ProxyFix using an explicitly configured
    proxy count. Reading X-Forwarded-For directly here would trust spoofable input.
    """

    return request.remote_addr


def _record_result(username: str, result: AuthResult) -> None:
    record_login_attempt(
        username=username,
        source=result.source,
        success=result.success,
        reason=result.reason,
        user_id=result.user.id if result.user else None,
    )


def _complete_successful_login(form: LoginForm, result: AuthResult):
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
        remember_requested=bool(form.remember.data),
    )

    return redirect(url_for('welcome.index'))


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit(
    lambda: current_app.config.get('AUTH_LOGIN_RATE_LIMIT', '5 per minute'),
    methods=['POST'],
)
def login():
    if current_user.is_authenticated:
        return redirect(url_for('welcome.index'))

    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data or ''
        password = form.password.data or ''
        result = authenticate(username, password)
        _record_result(username, result)

        if result.success and result.user:
            return _complete_successful_login(form, result)

        if result.reason == 'database_unavailable':
            message = result.message or DATABASE_UNAVAILABLE_MESSAGE
        else:
            message = result.message or INVALID_LOGIN_MESSAGE
        flash(message, 'danger')

    return render_template('auth/index.html', form=form)


@auth_bp.route('/logout', methods=['POST'])
def logout():
    logout_user()
    clear_authenticated_session()
    return redirect(url_for('auth.login'))
