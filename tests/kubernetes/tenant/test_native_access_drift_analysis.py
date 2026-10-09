from __future__ import annotations

from types import SimpleNamespace

from app.kubernetes.tenant.access_drift_analysis import classify_native_access_observation


def _grant(
    public_id: str = 'grant-1',
    *,
    status: str = 'active',
    scope_type: str = 'namespace',
    namespace: str = 'sandbox',
):
    record = SimpleNamespace(namespace=namespace)
    return SimpleNamespace(
        public_id=public_id,
        status=status,
        scope_type=scope_type,
        namespace=record,
        access_profile='viewer',
        access_profile_version=1,
        environment=SimpleNamespace(namespaces=[record]),
        tenant=SimpleNamespace(environments=[SimpleNamespace(namespaces=[record])]),
    )


def _binding(
    *,
    ownership: str = 'kaori_correlated',
    public_id: str = 'grant-1',
    namespace: str = 'sandbox',
    role_kind: str = 'Role',
    role_name: str = 'kaori-tenant-viewer-v1',
    binding_name: str = 'kaori-tenant-grant-grant-1',
) -> dict:
    return {
        'namespace': namespace,
        'name': binding_name,
        'ownership': ownership,
        'kaori_grant_id': public_id if ownership == 'kaori_correlated' else None,
        'claimed_grant_marker': public_id if ownership == 'kaori_marker_unverified' else None,
        'role_ref': {'kind': role_kind, 'name': role_name},
    }


def test_native_matching_active_grant_declaration_has_no_false_drift():
    findings = classify_native_access_observation(
        {'bindings': [_binding()]}, [_grant()]
    )
    assert findings == []


def test_native_external_and_unverified_marker_never_become_managed_access():
    findings = classify_native_access_observation(
        {'bindings': [
            _binding(ownership='external_observed', binding_name='foreign-viewer'),
            _binding(ownership='kaori_marker_unverified', binding_name='forged-kaori'),
        ]},
        [],
    )
    assert {row['code'] for row in findings} == {
        'external_native_rolebinding', 'unverified_kaori_grant_marker'
    }
    assert {row['severity'] for row in findings} == {'warning', 'critical'}


def test_native_revoked_grant_and_missing_active_grant_are_distinct():
    revoked = _grant(status='revoked')
    missing = _grant(public_id='grant-2')
    findings = classify_native_access_observation(
        {'bindings': [_binding()]}, [revoked, missing]
    )
    assert {row['code'] for row in findings} == {
        'revoked_grant_still_declared', 'active_grant_missing_native_declaration'
    }


def test_native_role_ref_mismatch_or_scope_expansion_requires_review():
    wrong_role = classify_native_access_observation(
        {'bindings': [_binding(role_kind='ClusterRole')]}, [_grant()]
    )
    assert [row['code'] for row in wrong_role] == ['native_grant_role_reference_mismatch']

    wrong_scope = classify_native_access_observation(
        {'bindings': [_binding(namespace='another-tenant')]}, [_grant()]
    )
    assert [row['code'] for row in wrong_scope] == ['native_grant_scope_mismatch']


def test_native_correlated_marker_of_another_tenant_is_rejected():
    findings = classify_native_access_observation(
        {'bindings': [_binding(public_id='grant-outside')]}, [_grant()]
    )
    assert {row['code'] for row in findings} == {
        'unresolved_native_rolebinding_ownership',
        'active_grant_missing_native_declaration',
    }
