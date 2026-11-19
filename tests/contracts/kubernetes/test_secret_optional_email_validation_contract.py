"""Optional registry email validation must preserve shape without regex backtracking."""

from __future__ import annotations

import pytest

from app.kubernetes.operations.secrets.validation import validate_optional_email


@pytest.mark.parametrize(
    'email',
    [
        '',
        'ops@example.invalid',
        'name+alias@sub.example.invalid',
        'a@b.c',
    ],
)
def test_optional_registry_email_accepts_existing_valid_shapes(email: str) -> None:
    validate_optional_email(email)


@pytest.mark.parametrize(
    'email',
    [
        'missing-at.invalid',
        '@example.invalid',
        'ops@',
        'ops@example',
        'ops@.invalid',
        'ops@example.',
        'ops@@example.invalid',
        'ops@example invalid',
        'ops\n@example.invalid',
        'ops@example.invalid\t',
        'ops@' + 'part.' * 4096,
    ],
)
def test_optional_registry_email_rejects_invalid_or_adversarial_shapes(email: str) -> None:
    with pytest.raises(ValueError, match='Registry email address is invalid'):
        validate_optional_email(email)
