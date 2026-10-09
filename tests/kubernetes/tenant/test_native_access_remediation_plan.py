from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.kubernetes.tenant.access_remediation_plan import classify_access_remediation


def _grant(*, status='active', reconciliation_status='drifted'):
    return SimpleNamespace(
        public_id='grant-native', id=42,
        status=status, reconciliation_status=reconciliation_status,
    )


def test_native_missing_managed_grant_uses_explicit_existing_reconcile_only():
    findings = [
        {'code': 'active_grant_missing_native_declaration', 'subject': 'grant-native'},
        {'code': 'external_native_rolebinding', 'subject': 'foreign-read'},
        {'code': 'unverified_kaori_grant_marker', 'subject': 'foreign-marker'},
        {'code': 'native_grant_scope_mismatch', 'subject': 'grant-native'},
        {'code': 'revoked_grant_still_declared', 'subject': 'grant-native'},
    ]
    result = classify_access_remediation(
        findings, [_grant()], authority_ready=True, provider_key='native_kubernetes',
    )
    assert result[0]['decision'] == 'explicit_grant_reconcile'
    assert result[0]['grant_id'] == 42
    assert all(row['decision'] == 'manual_review' for row in result[1:])
    assert all(row['auto_execute'] is False for row in result)


@pytest.mark.parametrize('status,reconciliation_status,authority', [
    ('revoked', 'drifted', True),
    ('active', 'ready', True),
    ('active', 'drifted', False),
])
def test_native_unready_or_revoked_grants_are_manual_only(status, reconciliation_status, authority):
    result = classify_access_remediation(
        [{'code': 'active_grant_missing_native_declaration', 'subject': 'grant-native'}],
        [_grant(status=status, reconciliation_status=reconciliation_status)],
        authority_ready=authority, provider_key='native_kubernetes',
    )
    assert result[0]['decision'] == 'manual_review'
    assert result[0]['grant_id'] is None
    assert result[0]['auto_execute'] is False


def test_capsule_and_native_codes_are_never_cross_admitted():
    rows = [{'code': 'active_grant_missing_capsule_declaration', 'subject': 'grant-native'}]
    assert classify_access_remediation(
        rows, [_grant()], authority_ready=True, provider_key='native_kubernetes'
    )[0]['decision'] == 'manual_review'

    rows = [{'code': 'active_grant_missing_native_declaration', 'subject': 'grant-native'}]
    assert classify_access_remediation(
        rows, [_grant()], authority_ready=True, provider_key='capsule'
    )[0]['decision'] == 'manual_review'
