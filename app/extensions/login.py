from __future__ import annotations

from flask import redirect, request, session, url_for
from flask_login import LoginManager
from sqlalchemy.exc import SQLAlchemyError

from app.auth.admission import session_admission_reason
from app.auth.readiness import check_authentication_database_readiness
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
        user = User.query.get(int(user_id))
        if user is None:
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
