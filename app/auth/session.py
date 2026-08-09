from __future__ import annotations

from urllib.parse import urlsplit

from flask import current_app, session
from flask_login import login_user

from app.models.user import User


class AuthSessionError(RuntimeError):
    pass


def safe_next_url(value: object) -> str | None:
    """Return a same-origin relative redirect target or ``None``.

    Only absolute-path references are accepted. Schemes, authorities,
    protocol-relative URLs, backslashes, and control characters are rejected so
    login and SSO callbacks cannot become open-redirect boundaries.
    """

    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or not candidate.startswith('/') or candidate.startswith('//'):
        return None
    if '\\' in candidate or any(ord(character) < 32 or ord(character) == 127 for character in candidate):
        return None

    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc:
        return None
    if not parsed.path.startswith('/') or parsed.path.startswith('//'):
        return None
    return candidate


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
    established = login_user(user, remember=remember, fresh=True)
    if not established:
        session.clear()
        raise AuthSessionError('Flask-Login rejected the authenticated user session.')
    session['auth_source'] = source

    return remember


def clear_authenticated_session() -> None:
    """Remove auth-owned state without losing Flask-Login cookie revocation."""

    remember_instruction = session.get('_remember')
    session.clear()
    if remember_instruction == 'clear':
        # ``logout_user()`` uses this marker in its after-request hook to expire
        # the persistent remember cookie. Preserve it across the domain cleanup.
        session['_remember'] = 'clear'
