from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_capsule_registry_and_discovery_share_one_attachment_service():
    routes = (ROOT / 'app/kubernetes/tenant/routes.py').read_text()
    service = (ROOT / 'app/kubernetes/tenant/discovery_adoption.py').read_text()
    # The reviewed Registry routes operators through Discovery's governed preflight,
    # rather than an inline provider-attachment form in the compact Registry table.
    discovery = (ROOT / 'app/templates/kubernetes/tenant/partials/_tenant_discovery.html').read_text()
    preflight = (ROOT / 'app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight.html').read_text()
    context = (ROOT / 'app/kubernetes/tenant/registry_context.py').read_text()
    assert 'def attach_discovered_capsule_namespace_committed(' in service
    assert 'def attach_capsule_namespace_to_existing_tenant_committed(' not in service
    assert 'attach_discovered_capsule_namespace_committed(source)' in routes
    assert "'provider_resource_version': str(" in routes
    assert "@permission_required('tenant.manage')" in routes
    assert 'attach_discovered_capsule_namespace_committed(request.form)' in routes
    assert "url_for('tenant.tenant_adoption_preflight_route'" in discovery
    assert 'data-tenant-adoption-load' in discovery
    assert 'Review Attachment' in discovery
    assert "url_for('tenant.adopt_discovered_tenant_route')" in preflight
    assert 'name="provider_uid"' in preflight
    assert 'name="provider_resource_version"' in preflight
    assert 'name="attach_environment_id"' in preflight
    assert 'name="csrf_token"' in preflight
    assert 'hx-target="#tenant-admin-workspace"' in preflight
    assert 'capsule_environment_options' in context
