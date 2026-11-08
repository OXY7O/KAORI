from __future__ import annotations

from types import SimpleNamespace

from app.kubernetes.tenant.access_drift_analysis import classify_tenant_access_observation


def _grant(public_id: str, status: str = 'active'):
    return SimpleNamespace(public_id=public_id, status=status)


def test_access_drift_correlation_distinguishes_external_orphan_and_revoked_declarations():
    snapshot = {
        'owners': [{'kind': 'User', 'name': 'outside-admin'}],
        'bindings': [
            {'ownership': 'external', 'cluster_role_name': 'view'},
            {'ownership': 'kaori', 'kaori_grant_id': 'active-a', 'cluster_role_name': 'viewer-v1'},
            {'ownership': 'kaori', 'kaori_grant_id': 'revoked-b', 'cluster_role_name': 'viewer-v1'},
            {'ownership': 'kaori', 'kaori_grant_id': 'unknown-c', 'cluster_role_name': 'viewer-v1'},
        ],
    }
    findings = classify_tenant_access_observation(
        snapshot, [_grant('active-a'), _grant('revoked-b', 'revoked'), _grant('active-d')]
    )
    codes = {finding['code'] for finding in findings}
    assert codes == {
        'external_capsule_owner',
        'external_access_review',
        'revoked_grant_still_declared',
        'orphaned_kaori_grant_marker',
        'active_grant_missing_capsule_declaration',
    }
    assert all(finding['action'] for finding in findings)
    assert {f['severity'] for f in findings} == {'critical', 'warning'}


def test_matching_active_capsule_declaration_has_no_false_finding():
    snapshot = {
        'owners': [],
        'bindings': [
            {'ownership': 'kaori', 'kaori_grant_id': 'grant-ok', 'cluster_role_name': 'kaori-tenant-viewer-v1'}
        ],
    }
    assert classify_tenant_access_observation(snapshot, [_grant('grant-ok')]) == []


def test_external_only_observation_never_infers_internal_grant():
    snapshot = {
        'owners': [],
        'bindings': [{'ownership': 'external', 'cluster_role_name': 'custom-viewer', 'subjects': []}],
    }
    findings = classify_tenant_access_observation(snapshot, [])
    assert len(findings) == 1
    assert findings[0]['code'] == 'external_access_review'
