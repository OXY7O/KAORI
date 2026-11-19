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
        'a@b..c',  # Existing permissive shape permits consecutive domain dots.
        'name@sub.例',  # Prior Unicode/non-ASCII shape remains accepted.
        'ops@' + 'part.' * 4096 + 'invalid',  # Long, well-formed input remains valid.
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
        'ops@domain.\u00a0invalid',  # Unicode no-break space is invalid whitespace.
        'ops@domain.\u2028invalid',  # Unicode line separator is invalid whitespace.
        'ops@domain.invalid\r',
        'ops@' + 'part.' * 4096 + '@invalid',  # Extra at-sign after long domain.
        'ops@' + 'part.' * 4096,
    ],
)
def test_optional_registry_email_rejects_invalid_or_adversarial_shapes(email: str) -> None:
    with pytest.raises(ValueError) as raised:
        validate_optional_email(email)
    assert str(raised.value) == 'Registry email address is invalid.'
