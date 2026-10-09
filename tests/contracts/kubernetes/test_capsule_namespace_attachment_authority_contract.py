from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_capsule_attachment_authority_is_read_only_and_reuses_provider_correlation():
    source = (ROOT / 'app/kubernetes/tenant/capsule_namespace_attachment_authority.py').read_text()
    assert 'def validate_capsule_existing_tenant_target(' in source
    assert 'def validate_capsule_namespace_attachment(' in source
    assert 'from app.kubernetes.tenant.allocation_observation import _CAPSULE_TENANT_LABEL_KEYS' in source
    assert "tenant.reconciliation_authority != 'capsule'" in source
    assert "tenant.lifecycle_status != 'ready'" in source
    assert "tenant.provider_evidence_json or {}).get('provider_uid')" in source
    assert "uid != expected_namespace_uid" in source
    assert "len(claims) > 1 or len(owners) > 1" in source
    assert "Namespace Capsule label belongs to another Tenant." in source
    assert "Namespace Capsule ownerReference belongs to another Tenant." in source
    assert "Namespace has no authoritative Capsule Tenant correlation." in source
    assert "'provider_mutation_performed': False" in source
    for forbidden in (
        'patch_namespace(', 'patch_cluster_custom_object(', 'delete_namespace(',
        'create_namespaced_role_binding(', 'db.session.commit()',
    ):
        assert forbidden not in source
