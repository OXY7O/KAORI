from __future__ import annotations

from app.auth.results import ACCESS_NOT_PERMITTED_MESSAGE, USER_INACTIVE_MESSAGE, AuthReason, AuthResult
from app.models.user import User


def session_admission_reason(user: User, *, source: str) -> AuthReason | None:
    if not user.is_active:
        return 'user_inactive'

    normalized_source = str(source or '').strip().lower()
    account_source = str(user.auth_source or '').strip().lower()

    if user.is_super_admin:
        if normalized_source != 'database' or account_source != 'database':
            return 'access_not_permitted'
        return None

    if account_source != normalized_source:
        return 'access_not_permitted'

    role = user.role_record
    if role is None or not role.is_active:
        return 'access_not_permitted'

    return None


def enforce_login_admission(result: AuthResult) -> AuthResult:
    if not result.success:
        return result

    user = result.user
    if user is None:
        return AuthResult(False, 'access_not_permitted', source=result.source, message=ACCESS_NOT_PERMITTED_MESSAGE)

    reason = session_admission_reason(user, source=result.source)
    if reason is None:
        return result

    return AuthResult(
        False,
        reason,
        source=result.source,
        user=user,
        message=USER_INACTIVE_MESSAGE if reason == 'user_inactive' else ACCESS_NOT_PERMITTED_MESSAGE,
    )
