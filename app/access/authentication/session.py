from __future__ import annotations

from secrets import token_hex
from urllib.parse import urlsplit

from flask import session
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

    Legacy ``<user_id>`` identifiers parse without a generation so admission
    can reject them explicitly. New identifiers use ``<user_id>:<generation>``.
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
    issued_session_version: int | None = None,
) -> bool:
    """Rotate the Flask session and establish an authenticated user session.

    Privileged human accounts never receive a persistent remember cookie.
    The login route applies the committed ordinary-account Remember Me policy;
    server-side deadlines also govern any remembered re-admission.
    """

    remember = bool(remember_requested and not user.is_admin_level)

    session.clear()
    established = login_user(user, remember=remember, fresh=True)
    if not established:
        session.clear()
        raise AuthSessionError('Flask-Login rejected the authenticated user session.')
    if issued_session_version is not None:
        if issued_session_version < 1:
            session.clear()
            raise AuthSessionError('Invalid issued authentication generation.')
        # Pin the generation returned by this login's atomic UPDATE. The ORM
        # may have expired and reloaded a later concurrent login's generation.
        # Flask-Login's remember-cookie hook reads this exact _user_id.
        session['_user_id'] = f'{user.id}:{issued_session_version}'
    if not remember:
        session['_remember'] = 'clear'
    session['auth_source'] = source
    # Audit correlation only. This opaque value is never an authentication
    # credential and cannot be used to look up or authorize a session.
    session['auth_session_ref'] = token_hex(16)

    return remember


def preserve_current_session_after_security_change(*, user_id: int, issued_session_version: int) -> None:
    """Bind only the authorized browser to the exact committed security generation.

    Never reload a newer concurrent login generation after the mutation commits.
    Remembered sign-ins are cleared and server-owned deadlines remain unchanged.
    """
    session['_user_id'] = f'{user_id}:{issued_session_version}'
    session['_fresh'] = True
    session['_remember'] = 'clear'
    session.modified = True


def preserve_current_session_after_password_change(*, user_id: int, issued_session_version: int) -> None:
    preserve_current_session_after_security_change(user_id=user_id, issued_session_version=issued_session_version)


def clear_authenticated_session() -> None:
    """Remove auth-owned state without losing Flask-Login cookie revocation."""

    remember_instruction = session.get('_remember')
    session.clear()
    if remember_instruction == 'clear':
        # ``logout_user()`` uses this marker in its after-request hook to expire
        # the persistent remember cookie. Preserve it across the domain cleanup.
        session['_remember'] = 'clear'
