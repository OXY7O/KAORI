from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_native_namespace_can_attach_to_existing_tenant_without_duplicate_tenant_creation():
    preflight = read('app/kubernetes/tenant/discovery_service.py')
    adoption = read('app/kubernetes/tenant/discovery_adoption.py')
    ui = read('app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight.html')
    routes = read('app/kubernetes/tenant/routes.py')

    assert "row = {" in preflight
    assert "'tenant_adoption_existing_environments': existing_tenant_environments" in preflight
    assert "Tenant.provider_key == 'native_kubernetes'" in preflight
    assert "Tenant.lifecycle_status == 'ready'" in preflight

    assert 'name="attach_environment_id"' in ui
    assert 'name="provider_uid"' in ui
    assert 'name="provider_resource_version"' in ui
    assert 'Attach to {{ option.tenant_name }}' in ui
    assert 'not expanded automatically' in ui

    assert 'def attach_discovered_native_namespace_committed(' in adoption
    assert "provider_key') or '') != 'native_kubernetes'" in adoption
    assert 'validate_namespace_attachment_uid(' in adoption
    assert 'validate_adoption_provider_identity(' in adoption
    assert "expected_resource_version=str(source.get('provider_resource_version')" in adoption
    assert '_native_management(' in adoption
    assert '_managed_namespace_map([cluster_id])' in adoption
    assert '_native_namespace_record(context, environment' in adoption
    assert '_take_over_native_allocation(context, record)' in adoption
    assert 'tenant.provider_evidence_json = existing_evidence' in adoption
    assert "'grants_expanded_automatically': False" in adoption
    assert 'reconcile_access_grants_for_namespace_committed(' not in adoption

    assert 'attach_discovered_native_namespace_committed(request.form)' in routes
    assert 'adopt_discovered_tenant_committed(request.form)' in routes
    assert "'Native Namespace Attached · Managed Allocation'" in routes
    assert "(namespace.provisioning_evidence_json or {}).get('provider_mutation_performed')" in routes
    assert "'operation': 'attach_existing_tenant_namespace' if attach_existing" in routes
    assert "'provider_mutation_may_have_started': not (" in routes
    assert 'KAORI database rollback' in routes
    assert "'attach_existing_tenant_namespace'" in routes
