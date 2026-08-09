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


def parse_authenticated_user_identifier(value: object) -> tuple[int, int | None]:
    """Parse Flask-Login's user identifier and optional credential generation.

    Legacy ``<user_id>`` identifiers are accepted only so sessions issued before
    the session-generation migration can be upgraded while the user remains on
    generation 1. New identifiers always use ``<user_id>:<generation>``.
    """

    normalized = str(value or '').strip()
    if not normalized:
        raise ValueError('Missing authenticated user identifier.')

    user_part, separator, version_part = normalized.partition(':')
    if separator and (not version_part or ':' in version_part):
        raise ValueError('Malformed authenticated user identifier.')

    user_id = int(user_part)
    if user_id <= 0:
        raise ValueError('Authenticated user identifier must be positive.')

    if not separator:
        return user_id, None

    version = int(version_part)
    if version <= 0:
        raise ValueError('Authentication session version must be positive.')
    return user_id, version


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


def preserve_current_session_after_password_change(user: User) -> None:
    """Keep this browser authenticated while revoking older credential sessions.

    ``User.set_password()`` advances ``auth_session_version``. Refreshing the
    current Flask-Login identifier binds this browser to the new generation,
    while other sessions keep their old identifier and fail closed on their next
    request. Any remember cookie is intentionally cleared so remembered sign-ins
    must authenticate again with the replacement password.
    """

    session['_user_id'] = user.get_id()
    session['_fresh'] = True
    session['_remember'] = 'clear'
    session.modified = True


def clear_authenticated_session() -> None:
    """Remove auth-owned state without losing Flask-Login cookie revocation."""

    remember_instruction = session.get('_remember')
    session.clear()
    if remember_instruction == 'clear':
        # ``logout_user()`` uses this marker in its after-request hook to expire
        # the persistent remember cookie. Preserve it across the domain cleanup.
        session['_remember'] = 'clear'
