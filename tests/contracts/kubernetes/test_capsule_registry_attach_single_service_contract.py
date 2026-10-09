from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_capsule_registry_and_discovery_share_one_attachment_service():
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text()
    service = (ROOT / 'app/kubernetes/tenant/discovery_adoption.py').read_text()
    ui = (ROOT / 'app/templates/kubernetes/tenant/partials/_tenant_registry.html').read_text()
    context = (ROOT / 'app/kubernetes/tenant/registry_context.py').read_text()
    assert "def attach_discovered_capsule_namespace_committed(" in service
    assert "def attach_capsule_namespace_to_existing_tenant_committed(" not in service
    assert "attach_discovered_capsule_namespace_committed(source)" in routes
    assert "'provider_resource_version': str(" in routes
    assert "@permission_required('tenant.manage')" in routes
    assert "name=\"namespace_resource_version\"" in ui
    assert "name=\"namespace_uid\"" in ui
    assert "name=\"csrf_token\"" in ui
    assert "hx-target=\"#tenant-admin-workspace\"" in ui
    assert "capsule_environment_options" in context
    assert "data-capsule-namespace-attach" in ui
