from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_capsule_attach_reuses_discovery_and_existing_tenant_provider_authority() -> None:
    discovery = read('app/kubernetes/tenant/discovery_service.py')
    adoption = read('app/kubernetes/tenant/discovery_adoption.py')
    route = read('app/kubernetes/tenant/routes.py')
    modal = read('app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight.html')
    table = read('app/templates/kubernetes/tenant/partials/_tenant_discovery.html')

    assert 'def select_capsule_namespace_attachment_candidate(' in discovery
    assert 'def _capsule_namespace_attachment_preflight(' in discovery
    assert '_capsule_namespace_correlation(' in discovery
    assert "'resource_kind': 'Capsule Namespace'" in discovery
    assert 'capsule_tenant_name: str' in discovery
    assert 'tenant_adoption_attachment_only' in discovery
    assert 'correlation_proven' in discovery
    assert 'namespace_items=namespace_items' in discovery

    assert 'def attach_discovered_capsule_namespace_committed(' in adoption
    assert "tenant.provider_key != 'capsule'" in adoption
    assert "tenant.reconciliation_authority != 'capsule'" in adoption
    assert 'select_capsule_namespace_attachment_candidate(' in adoption
    assert '_managed_namespace_map([cluster_id])' in adoption
    assert "expected_uid=str(source.get('provider_uid')" in adoption
    assert "expected_resource_version=str(source.get('provider_resource_version')" in adoption
    assert "_capsule_namespace_records(context, environment, scoped)" in adoption
    assert '_mirror_capsule_namespace_policies(tenant, records)' in adoption
    assert "'grants_expanded_automatically': False" in adoption
    assert "'provider_mutation_performed': False" in adoption
    assert 'tenant.provider_evidence_json = previous_evidence' in adoption
    assert 'db.session.commit()' in adoption

    assert 'attach_discovered_capsule_namespace_committed(request.form)' in route
    assert "provider_key == 'capsule'" in route
    assert "provider_key == 'native_kubernetes'" in route
    assert "Unsupported provider authority for existing-Tenant Namespace attachment." in route
    assert "attach_existing and str(request.form.get('capsule_tenant_name')" not in route
    assert "capsule_tenant_name=str(request.args.get('capsule_tenant_name')" in route
    assert '_csrf()' in route
    assert "name=\"capsule_tenant_name\"" in modal
    assert "name=\"provider_resource_version\"" in modal
    assert "name=\"attach_environment_id\" required" in modal
    assert 'Capsule Namespace → Existing Tenant' in modal
    assert 'capsule_tenant_name=row.capsule_tenant_name or' in table


def test_capsule_namespace_attachment_has_no_unreviewed_provider_write() -> None:
    source = read('app/kubernetes/tenant/discovery_adoption.py')
    block = source.split('def attach_discovered_capsule_namespace_committed(', 1)[1]
    block = block.split('def adopt_discovered_tenant_committed(', 1)[0]
    for forbidden in (
        'patch_namespace(', 'patch_namespaced_resource_quota(',
        'patch_cluster_custom_object(', 'delete_namespace(',
        'reconcile_adopted_native_allocation(', '_take_over_capsule_allocation(',
        'create_namespaced_role_binding(', 'reconcile_access_grant(',
    ):
        assert forbidden not in block
    assert '_mirror_capsule_namespace_policies' in block
    assert 'db.session.rollback()' in block
