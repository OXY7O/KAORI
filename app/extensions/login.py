from __future__ import annotations

from datetime import UTC, datetime

from flask import g, jsonify, redirect, request, session, url_for
from flask_login import LoginManager
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication.admission import session_admission_reason
from app.access.authentication.readiness import check_authentication_database_readiness
from app.access.authentication.session import parse_authenticated_user_identifier
from app.access.authentication.session_lifecycle import (
    SessionDeadlines,
    expire_generation,
    read_session_policy,
    session_deadlines,
)
from app.common.flashes import flash_once
from app.extensions.db import db
from app.models.user import User

login_manager = LoginManager()
login_manager.login_view = 'auth.login'  # pyright: ignore
# Authentication notifications are emitted by the custom unauthorized handler.
# Keeping Flask-Login's default message disabled prevents duplicate flashes.
login_manager.login_message = ''


@login_manager.user_loader
def load_user(user_id: str):
    """Resolve a session user without producing user-facing side effects.

    A user loader may run several times during one browser navigation.  It must
    therefore never flash.  Database readiness and notification decisions are
    handled once by the login route or unauthorized handler.
    """

    def invalidate_session() -> None:
        session.clear()
        # Clear a persistent remember cookie as well. Otherwise a revoked user
        # can be reloaded from the same cookie on the next request.
        session['_remember'] = 'clear'

    try:
        resolved_user_id, issued_session_version = parse_authenticated_user_identifier(user_id)
        user = User.query.get(resolved_user_id)
        if user is None:
            invalidate_session()
            return None

        current_session_version = max(int(user.auth_session_version or 1), 1)
        # Pre-migration legacy cookies have no trustworthy issued/idle state.
        if issued_session_version is None or issued_session_version != current_session_version:
            invalidate_session()
            return None

        source = str(session.get('auth_source') or user.last_auth_source or user.auth_source or '')
        if session_admission_reason(user, source=source) is not None:
            invalidate_session()
            return None

        policy = read_session_policy()
        # Flask-Login restores an identifier from a Remember Me cookie without
        # the auth_source established by a full successful authentication.
        # Never admit a privileged or policy-denied remembered-only session.
        if not session.get('auth_source') and (user.is_admin_level or not policy.regular_remember):
            invalidate_session()
            return None

        deadlines = session_deadlines(user, policy, datetime.now(UTC))
        if not isinstance(deadlines, SessionDeadlines):
            if not expire_generation(user, issued_session_version, deadlines):
                # A concurrent admitted activity refresh may have won the CAS.
                # Re-check the current generation and deadlines before denial.
                db.session.refresh(user)
                if user.auth_session_version == issued_session_version:
                    deadlines = session_deadlines(user, policy, datetime.now(UTC))
                    if isinstance(deadlines, SessionDeadlines) and session_admission_reason(user, source=source) is None:
                        g.kaori_session_policy = policy
                        g.kaori_session_deadlines = deadlines
                        return user
            g.kaori_session_expired = True
            invalidate_session()
            return None

        g.kaori_session_policy = policy
        g.kaori_session_deadlines = deadlines
        return user
    except (TypeError, ValueError):
        invalidate_session()
        return None
    except SQLAlchemyError:
        db.session.rollback()
        # Database unavailability is not proof of a revoked identity. Fail closed
        # for this request but retain the signed session for a subsequent retry.
        g.authentication_database_unavailable = True
        return None


@login_manager.unauthorized_handler
def handle_unauthorized():
    """Redirect unauthenticated requests with one context-appropriate message."""

    # A failed user load has already established database unavailability. Do not
    # issue a second pool checkout or redirect a signed-in user to the login form.
    if getattr(g, 'authentication_database_unavailable', False):
        return (
            'Authentication is temporarily unavailable. Please retry.',
            503,
            {'Cache-Control': 'no-store, max-age=0', 'Retry-After': '5'},
        )

    if request.endpoint in ('auth.session_status', 'auth.session_activity'):
        if getattr(g, 'kaori_session_expired', False):
            flash_once('Your session expired. Sign in again to continue.', 'warning')
        return jsonify({'status': 'reauthentication_required'}), 401, {'Cache-Control': 'no-store'}

    readiness = check_authentication_database_readiness()
    login_url = url_for('auth.login', next=request.full_path.rstrip('?'))

    # A fresh or unavailable database is explained by the setup page itself.
    # Flashing here would create misleading "Please sign in" notifications.
    if not readiness.ready:
        return redirect(login_url)

    if getattr(g, 'kaori_session_expired', False):
        flash_once('Your session expired. Sign in again to continue.', 'warning')
    else:
        flash_once('Please sign in to continue.', 'warning')
    if request.headers.get('HX-Request') == 'true':
        return '', 401, {'HX-Redirect': login_url, 'Cache-Control': 'no-store'}
    return redirect(login_url)
