from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_existing_release_preflight_reuses_provider_handoff_normalizer_and_commits_evidence():
    service = read('app/kubernetes/tenant/release_preflight.py')
    normalizer = read('app/kubernetes/tenant/release_handoff_inventory.py')
    registry = read('app/templates/kubernetes/tenant/partials/_tenant_registry.html')

    assert 'def review_tenant_release_preflight_committed(' in service
    assert 'observe_native_namespace_allocation(' in service
    assert 'native_namespace_handoff_evidence(' in service
    assert 'capsule_tenant_handoff_evidence(' in service
    assert "'handoff_components': handoff_components" in service
    assert "'handoff_fingerprint': handoff_fingerprint(handoff_components)" in service
    assert "'handoff_required_count': sum(" in service
    assert "previous.get('handoff_fingerprint') != latest.get('handoff_fingerprint')" in service
    assert 'capsule_namespace_handoff_evidence(' in service
    assert '_capsule_status_namespace_names(obj)' in service
    assert "'provider_resource_deleted': False" in service

    assert 'kaori_marker_correlated' in normalizer
    assert 'marker_conflict' in normalizer
    assert "'external_acceptance_required'" in normalizer
    assert 'def handoff_fingerprint(' in normalizer
    assert 'patch_namespace(' not in normalizer
    assert 'delete_namespace(' not in normalizer
    assert 'patch_namespaced_resource_quota(' not in normalizer
    assert 'patch_namespaced_limit_range(' not in normalizer

    assert 'Handoff inventory' in registry
    assert 'row.release_preflight.handoff_components' in registry
    assert 'row.release_preflight.handoff_required_count' in registry
    assert 'View evidence' not in registry or 'Handoff inventory' in registry
