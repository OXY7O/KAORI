"""MFA setup-key errors stay actionable without exposing sensitive details (#3251)."""

from __future__ import annotations

import pytest

from app.access.authentication.mfa.service import MfaVerificationError
from app.settings.routes import _mfa_account_error_message


@pytest.mark.parametrize(
    ('reason', 'expected'),
    [
        ('Sign in again before changing MFA.', 'Sign out and sign back in'),
        ('Your current password was not accepted.', 'Verify your password'),
        ('MFA is already enrolled.', 'recovery section'),
        ('Start MFA enrollment again.', 'Generate a new setup key'),
        ('MFA enrollment expired; start again.', 'Setup key expired'),
        ('Verification code was not accepted.', 'Check your authenticator time'),
    ],
)
def test_mfa_setup_rejection_explains_safe_next_step(reason: str, expected: str) -> None:
    assert expected in _mfa_account_error_message(MfaVerificationError(reason))


def test_unknown_failure_cannot_leak_sensitive_exception_details() -> None:
    secret = 'TOP_SECRET_SAMPLE_DO_NOT_LOG'
    result = _mfa_account_error_message(MfaVerificationError(secret))
    assert secret not in result
    assert 'Verify your session' in result


def test_existing_route_distinguishes_expired_form_and_service_errors() -> None:
    from pathlib import Path

    routes = (
        Path(__file__).resolve().parents[3] / 'app/settings/routes.py'
    ).read_text(encoding='utf-8')
    assert "validate_csrf(request.form.get('csrf_token'))" in routes
    assert "if not login_fresh():" in routes
    assert "if action in {'begin', 'regenerate'} and user.auth_source == 'database':" in routes
    assert 'mfa_setup_secret = begin_mfa_enrollment(user)' in routes
    assert 'except ValidationError:' in routes
    assert 'except MfaVerificationError as exc:' in routes
    assert 'mfa_feedback = _mfa_account_error_message(exc)' in routes
    assert "response.headers['Cache-Control'] = 'no-store'" in routes
