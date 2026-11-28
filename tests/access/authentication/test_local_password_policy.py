"""Shared local password policy regression (#5328)."""

import pytest
from wtforms import Form, PasswordField

from app.access.authentication.password_policy import (
    LOCAL_PASSWORD_MAX_LENGTH,
    LOCAL_PASSWORD_MIN_LENGTH,
    LocalPasswordPolicy,
    local_password_policy_error,
)


@pytest.mark.parametrize(
    'value',
    ('password1234', 'PASSWORDPASSWORD', '123456789012', 'administrator', 'kaoriadmin123'),
)
def test_known_weak_passwords_meeting_minimum_are_rejected(value: str) -> None:
    assert len(value) >= LOCAL_PASSWORD_MIN_LENGTH
    assert local_password_policy_error(value) == 'Choose a stronger password that is not a known default value.'


def test_local_password_length_boundaries() -> None:
    assert local_password_policy_error('x' * (LOCAL_PASSWORD_MIN_LENGTH - 1))
    assert local_password_policy_error('x' * LOCAL_PASSWORD_MIN_LENGTH) is None
    assert local_password_policy_error('x' * LOCAL_PASSWORD_MAX_LENGTH) is None
    assert local_password_policy_error('x' * (LOCAL_PASSWORD_MAX_LENGTH + 1))


def test_unique_passphrase_is_accepted() -> None:
    assert local_password_policy_error('A sample long passphrase for testing only') is None


def test_wtforms_policy_flags_match_server_validation() -> None:
    class PasswordForm(Form):
        password = PasswordField(validators=[LocalPasswordPolicy()])

    form = PasswordForm()
    assert form.password.flags.minlength == LOCAL_PASSWORD_MIN_LENGTH
    assert form.password.flags.maxlength == LOCAL_PASSWORD_MAX_LENGTH
