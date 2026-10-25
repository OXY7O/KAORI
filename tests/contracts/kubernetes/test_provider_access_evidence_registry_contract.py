"""Tenant provider inspection evidence must remain paged, scoped and read-only."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_provider_access_evidence_queries_are_committed_and_paged() -> None:
    service = read('app/kubernetes/tenant/access_service.py')
    routes = read('app/kubernetes/tenant/route_common.py')
    assert 'def get_provider_access_evidence_registry_context(' in service
    assert "'capsule': 'kubernetes_tenant_external_access_inventory'" in service
    assert "'native': 'kubernetes_tenant_native_external_access_inventory'" in service
    assert 'raise ValueError(\'Unknown Tenant access inspection provider.\')' in service
    assert 'AuditEvent.query.filter(AuditEvent.target_type == target_types[provider])' in service
    assert 'query.order_by(AuditEvent.id.desc())' in service
    assert 'paginate_query(' in service
    assert "'access_evidence_total': total_committed" in service
    assert "status in {'observed', 'review_required'}" in service
    assert "AuditEvent.metadata_json['status'].as_string()" in service
    assert "AuditEvent.metadata_json['tenant_id'].as_string().ilike(pattern)" in service
    assert 'AuditEvent.summary.ilike(pattern)' in service
    assert 'get_provider_access_evidence_registry_context(' in routes
    assert "if active_view in {'capsule', 'native'}" in routes
    assert "_query_int('access_evidence_per_page', 5)" in routes
    assert "_query_text('access_evidence_status')" in routes
    assert "_query_text('access_evidence_search')" in routes


def test_both_provider_registries_reuse_standard_filter_and_pagination() -> None:
    for provider, template_path in (
        ('capsule', 'app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html'),
        ('native', 'app/templates/kubernetes/tenant/partials/_native_namespace_rbac_inventory.html'),
    ):
        panel = read(template_path)
        assert 'components/table_registry.html' in panel
        assert 'components/table.html' in panel
        assert "registry_ui.filter_form('tenant.tenants'" in panel
        assert "registry_ui.clear_filters_link('tenant.tenants'" in panel
        assert "registry_ui.footer('tenant.tenants'" in panel
        assert "page_param='access_evidence_page'" in panel
        assert "per_page_param='access_evidence_per_page'" in panel
        assert "access_evidence_pagination.allowed_per_page" in panel
        assert "'access_inventory_view': '" + provider + "'" in panel
        assert 'name="access_inventory_view" value="' + provider + '"' in panel
        assert '{% for event in access_evidence_rows %}' in panel
        assert 'access_evidence_filters.status' in panel
        assert 'access_evidence_filters.search' in panel
        assert 'name="access_evidence_status"' in panel
        assert "'access_evidence_search'" in panel
        assert 'access_evidence_total }} records' in panel
        assert 'sm:min-h-52 sm:py-12' in panel
        assert 'No matching inspections found.' in panel
        assert 'role="status"' in panel
        assert 'event.created_at|user_datetime' in panel
        assert 'hx-' not in panel.split('Inspection Target', 1)[0]  # No implicit live-provider request


def test_native_subtitle_and_provider_safety_boundaries_remain_explicit() -> None:
    native = read('app/templates/kubernetes/tenant/partials/_native_namespace_rbac_inventory.html')
    capsule = read('app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html')
    assert 'Inspect Namespace RoleBindings read-only without changing RBAC or identities.' in native
    assert 'No membership or RBAC mutation occurs' in capsule
    assert 'does not import IdP users' in capsule
    assert 'Labels indicate possible correlation' in native
    assert 'No automatic remediation was performed.' in native
    assert 'Inspect External Access' in capsule
    assert 'Inspect Native RBAC' in native
    assert 'Review Profile Match' in capsule
    assert 'Review Profile Match' in native
    for panel in (capsule, native):
        assert 'name="csrf_token"' in panel
        assert 'Not inspected' in panel
        assert 'Committed Evidence' in panel
        assert 'Provider Authority' in panel
