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



def test_capsule_attachment_reuses_canonical_profile_mirror_and_live_ownership_guard():
    adoption = (ROOT / 'app/kubernetes/tenant/discovery_adoption.py').read_text()
    registry = (ROOT / 'app/templates/kubernetes/tenant/partials/_tenant_registry.html').read_text()
    context = (ROOT / 'app/kubernetes/tenant/registry_context.py').read_text()
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text()

    assert 'def attach_capsule_namespace_to_existing_tenant_committed(' in adoption
    assert 'validate_capsule_namespace_attachment(' in adoption
    assert 'observe_capsule_tenant_allocation(' in adoption
    assert '_managed_namespace_map([str(cluster.id)])' in adoption
    assert '_verify_released_namespace_lineage(' in adoption
    assert '_capsule_namespace_records(context, environment, selected_allocation)' in adoption
    assert '_mirror_capsule_namespace_policies(tenant, records)' in adoption
    assert "'grants_expanded_automatically': False" in adoption
    assert "'provider_mutation_performed': False" in adoption
    assert 'db.session.commit()' in adoption

    assert "@tenant_bp.post('/capsule/namespace-attach')" in routes
    assert 'attach_existing_capsule_namespace_route' in routes
    assert "attach_capsule_namespace_to_existing_tenant_committed(" in routes
    assert '_csrf()' in routes

    assert 'capsule_environment_map' in context
    assert "'capsule_environment_options'" in context
    assert 'data-capsule-namespace-attach' in registry
    assert "tenant.attach_existing_capsule_namespace_route" in registry
    assert 'name="namespace_uid"' in registry
    assert 'name="environment_id"' in registry
