from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_native_handoff_readback_has_no_provider_or_governance_mutation_path():
    preview = (ROOT / 'app/kubernetes/tenant/native_handoff_dry_run.py').read_text()
    readback = (ROOT / 'app/kubernetes/tenant/native_handoff_readback.py').read_text()
    route = (ROOT / 'app/kubernetes/tenant/routes.py').read_text()
    registry = (ROOT / 'app/templates/kubernetes/tenant/partials/_tenant_registry.html').read_text()
    assert "'spec_sha256': _stable_sha256(_spec(before))" in preview
    assert "'retained_metadata_sha256': _stable_sha256(" in preview
    assert "verify_external_native_component(" in readback
    assert "'external_successor_verified': False" in readback
    assert "'provider_handoff_verified': False" in readback
    assert "'release_authorized': False" in readback
    assert "inspect_native_external_handoff_route" in route
    assert "Verify Provider Read-Back" in registry
    for forbidden in [
        'patch_namespace(', 'create_namespace(', 'delete_namespace(',
        'release_adopted_tenant_committed(', 'reconcile_native_access_grant(',
        'create_access_grant_committed(', 'delete_namespaced_role_binding(',
    ]:
        assert forbidden not in readback
