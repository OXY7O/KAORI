from datetime import UTC, datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user

from app.auth.audit import record_login_attempt
from app.auth.forms import LoginForm
from app.auth.services import DATABASE_UNAVAILABLE_MESSAGE, INVALID_LOGIN_MESSAGE, authenticate
from app.extensions import db, limiter

# Initialize the authentication blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def _get_client_ip() -> str | None:
    forwarded_for = request.headers.get('X-Forwarded-For')

    if forwarded_for:
        return forwarded_for.split(',')[0].strip() or None

    return request.remote_addr


# Route for user login
@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit(
    lambda: current_app.config.get('AUTH_LOGIN_RATE_LIMIT', '5 per minute'),
    methods=['POST'],
)
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.welcome'))

    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data or ''
        password = form.password.data or ''

        result = authenticate(username, password)
        record_login_attempt(
            username=username,
            source=result.source,
            success=result.success,
            reason=result.reason,
            user_id=result.user.id if result.user else None,
        )

        if result.success and result.user:
            result.user.last_login_at = datetime.now(UTC)
            result.user.last_login_ip = _get_client_ip()
            result.user.last_auth_source = result.source
            db.session.commit()

            login_user(result.user, remember=form.remember.data)
            session['auth_source'] = result.source

            return redirect(url_for('dashboard.welcome'))

        if result.reason == 'database_unavailable':
            flash(result.message or DATABASE_UNAVAILABLE_MESSAGE, 'danger')
        else:
            flash(result.message or INVALID_LOGIN_MESSAGE, 'danger')

    return render_template('auth/index.html', form=form)


# Route for user logout
@auth_bp.route('/logout')
def logout():
    logout_user()

    session.pop('auth_source', None)
    session.pop('_flashes', None)

    return redirect(url_for('auth.login'))
