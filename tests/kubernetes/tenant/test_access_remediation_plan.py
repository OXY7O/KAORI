from __future__ import annotations

from types import SimpleNamespace

from app.kubernetes.tenant.access_remediation_plan import classify_access_remediation


def _grant(public_id, status='active', reconciliation='drifted', id=17):
    return SimpleNamespace(
        public_id=public_id, id=id, status=status, reconciliation_status=reconciliation
    )


def test_only_kaori_owned_active_drifted_grant_qualifies_for_explicit_existing_reconcile():
    findings = [
        {'code': 'active_grant_missing_capsule_declaration', 'subject': 'grant-a'},
        {'code': 'external_access_review', 'subject': 'role-view'},
        {'code': 'orphaned_kaori_grant_marker', 'subject': 'grant-orphan'},
        {'code': 'revoked_grant_still_declared', 'subject': 'grant-revoked'},
    ]
    result = classify_access_remediation(findings, [_grant('grant-a')], authority_ready=True)
    assert result[0]['decision'] == 'explicit_grant_reconcile'
    assert result[0]['grant_id'] == 17
    assert all(item['decision'] == 'manual_review' for item in result[1:])
    assert all(item['auto_execute'] is False for item in result)


def test_ready_revoked_or_degraded_principal_never_enters_automatic_remediation():
    findings = [{'code': 'active_grant_missing_capsule_declaration', 'subject': 'grant-a'}]
    for grant, authority in [
        (_grant('grant-a', reconciliation='ready'), True),
        (_grant('grant-a', status='revoked'), True),
        (_grant('grant-a'), False),
    ]:
        result = classify_access_remediation(findings, [grant], authority_ready=authority)
        assert result[0]['decision'] == 'manual_review'
        assert result[0]['grant_id'] is None
        assert result[0]['auto_execute'] is False
