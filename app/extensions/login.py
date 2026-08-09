from __future__ import annotations

from flask import redirect, request, session, url_for
from flask_login import LoginManager
from sqlalchemy.exc import SQLAlchemyError

from app.auth.admission import session_admission_reason
from app.auth.readiness import check_authentication_database_readiness
from app.auth.session import parse_authenticated_user_identifier
from app.common.flashes import flash_once
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
        if issued_session_version is None:
            # Legacy sessions issued before session generations existed are only
            # admissible while the account remains on its initial generation.
            # Once a password has changed, a missing generation fails closed.
            if current_session_version != 1:
                invalidate_session()
                return None
            session['_user_id'] = user.get_id()
        elif issued_session_version != current_session_version:
            invalidate_session()
            return None

        source = str(session.get('auth_source') or user.last_auth_source or user.auth_source or '')
        if session_admission_reason(user, source=source) is not None:
            invalidate_session()
            return None
        return user
    except (TypeError, ValueError):
        invalidate_session()
        return None
    except SQLAlchemyError:
        invalidate_session()
        return None


@login_manager.unauthorized_handler
def handle_unauthorized():
    """Redirect unauthenticated requests with one context-appropriate message."""

    readiness = check_authentication_database_readiness()
    login_url = url_for('auth.login', next=request.full_path.rstrip('?'))

    # A fresh or unavailable database is explained by the setup page itself.
    # Flashing here would create misleading "Please sign in" notifications.
    if not readiness.ready:
        return redirect(login_url)

    flash_once('Please sign in to continue.', 'warning')
    return redirect(login_url)
