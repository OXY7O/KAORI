from __future__ import annotations

from flask import current_app, session
from flask_login import login_user

from app.models.user import User


def establish_authenticated_session(
    user: User,
    *,
    source: str,
    remember_requested: bool,
) -> bool:
    """Rotate the Flask session and establish an authenticated user session.

    Super-admin sessions do not become persistent unless an operator explicitly
    enables that behavior. This keeps the local recovery account suitable for
    break-glass use without changing the normal-user login experience.
    """

    allow_super_admin_remember = bool(current_app.config.get('AUTH_ALLOW_SUPER_ADMIN_REMEMBER_ME', False))
    remember = bool(remember_requested and (not user.is_super_admin or allow_super_admin_remember))

    session.clear()
    login_user(user, remember=remember, fresh=True)
    session['auth_source'] = source

    return remember


def clear_authenticated_session() -> None:
    """Remove authentication and step-up state owned by the auth domain."""

    session.clear()
