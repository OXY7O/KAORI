from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_capsule_attach_canonical_service_has_strict_provider_readback_and_owner_proof():
    authority = (ROOT / 'app/kubernetes/tenant/capsule_namespace_attachment_authority.py').read_text()
    service = (ROOT / 'app/kubernetes/tenant/discovery_adoption.py').read_text()
    assert "def validate_capsule_namespace_attachment(" in authority
    assert "owner, 'uid') != capsule_uid" in authority
    assert "validate_capsule_namespace_attachment(" in service
    assert "proof['namespace_resource_version'] != selected['resource_version']" in service
    assert "_capsule_status_namespace_names(tenant_cr)" in service
    assert "verified_tenant_cr = _read_capsule_tenant(" in service
    assert "verified_namespace = client.core_api().read_namespace(" in service
    assert "'capsule_authority': proof" in service
    for forbidden in ("patch_namespace(", "delete_namespace(", "delete_namespaced_role_binding("):
        assert forbidden not in authority
