from __future__ import annotations

from wtforms.validators import ValidationError

LOCAL_PASSWORD_MIN_LENGTH = 12
LOCAL_PASSWORD_MAX_LENGTH = 1024
BLOCKED_LOCAL_PASSWORDS = frozenset(
    {
        'admin',
        'changeme',
        'change-me',
        'password',
        'password123',
        'kaori',
    }
)


def local_password_policy_error(value: object) -> str | None:
    """Return a user-safe Local Database password policy error, if any."""

    password = str(value or '')
    if len(password) < LOCAL_PASSWORD_MIN_LENGTH:
        return f'Password must be at least {LOCAL_PASSWORD_MIN_LENGTH} characters.'
    if len(password) > LOCAL_PASSWORD_MAX_LENGTH:
        return f'Password must be at most {LOCAL_PASSWORD_MAX_LENGTH} characters.'
    if password.casefold() in BLOCKED_LOCAL_PASSWORDS:
        return 'Choose a stronger password that is not a known default value.'
    return None


class LocalPasswordPolicy:
    """WTForms validator for KAORI-owned Local Database credentials."""

    def __call__(self, form, field) -> None:  # noqa: ANN001
        error = local_password_policy_error(field.data)
        if error is not None:
            raise ValidationError(error)
