"""MFA assurance policy never establishes a session before required assurance (#3133)."""

import pytest

from app.access.authentication.mfa.policy import (
    MfaGate,
    MfaPolicyError,
    MfaPolicyMode,
    can_issue_session,
    evaluate_mfa_policy,
)


@pytest.mark.parametrize('privileged', [False, True])
@pytest.mark.parametrize('enrolled', [False, True])
def test_disabled_policy_keeps_current_login_behavior(privileged: bool, enrolled: bool) -> None:
    decision = evaluate_mfa_policy(MfaPolicyMode.DISABLED, privileged=privileged, enrolled=enrolled)
    assert decision.gate == MfaGate.ALLOW
    assert can_issue_session(decision)


@pytest.mark.parametrize(
    ('mode', 'privileged', 'enrolled', 'expected'),
    [
        ('optional', False, False, MfaGate.ALLOW),
        ('optional', True, False, MfaGate.ALLOW),
        ('optional', False, True, MfaGate.CHALLENGE),
        ('optional', True, True, MfaGate.CHALLENGE),
        ('required_privileged', False, False, MfaGate.ALLOW),
        ('required_privileged', True, False, MfaGate.ENROLLMENT_REQUIRED),
        ('required_privileged', True, True, MfaGate.CHALLENGE),
        ('required_privileged', False, True, MfaGate.CHALLENGE),
        ('required_all', False, False, MfaGate.ENROLLMENT_REQUIRED),
        ('required_all', True, False, MfaGate.ENROLLMENT_REQUIRED),
        ('required_all', False, True, MfaGate.CHALLENGE),
        ('required_all', True, True, MfaGate.CHALLENGE),
    ],
)
def test_post_primary_policy_gate(mode: str, privileged: bool, enrolled: bool, expected: MfaGate) -> None:
    decision = evaluate_mfa_policy(mode, privileged=privileged, enrolled=enrolled)
    assert decision.gate == expected
    assert decision.policy_required == (
        mode == 'required_all' or (mode == 'required_privileged' and privileged)
    )
    if expected == MfaGate.ALLOW:
        assert can_issue_session(decision)
    elif expected == MfaGate.CHALLENGE:
        assert not can_issue_session(decision)
        assert can_issue_session(decision, factor_verified=True)
    else:
        assert not can_issue_session(decision)
        assert not can_issue_session(decision, factor_verified=True)


@pytest.mark.parametrize('mode', ['', 'mandatory', 'Required All', None, False, 1])
def test_unsupported_configuration_fails_closed(mode: object) -> None:
    with pytest.raises(MfaPolicyError):
        evaluate_mfa_policy(mode, privileged=True, enrolled=True)


@pytest.mark.parametrize(('privileged', 'enrolled'), [('yes', True), (True, 1), (None, False)])
def test_ambiguous_principal_evidence_fails_closed(privileged: object, enrolled: object) -> None:
    with pytest.raises(MfaPolicyError):
        evaluate_mfa_policy('required_all', privileged=privileged, enrolled=enrolled)


def test_untrusted_verification_type_fails_closed() -> None:
    decision = evaluate_mfa_policy('required_all', privileged=True, enrolled=True)
    with pytest.raises(MfaPolicyError):
        can_issue_session(decision, factor_verified='yes')
