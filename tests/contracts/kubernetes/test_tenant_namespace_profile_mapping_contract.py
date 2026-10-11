"""Tenant Detail Namespace/Profile correlation remains bounded and committed (#1136)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
DETAIL = ROOT / "app/templates/kubernetes/tenant/partials/_tenant_management_detail.html"
PARTIAL = ROOT / "app/templates/kubernetes/tenant/partials/_tenant_namespace_profile_mapping.html"
CONTEXT = ROOT / "app/kubernetes/tenant/route_common.py"
REGISTRY = ROOT / "app/kubernetes/tenant/registry_context.py"


def source(path):
    return path.read_text(encoding="utf-8")


def test_tenant_detail_exposes_one_canonical_mapping_not_an_allocation_editor():
    detail, partial = source(DETAIL), source(PARTIAL)
    Environment().parse(detail)
    Environment().parse(partial)
    assert detail.count("_tenant_namespace_profile_mapping.html") == 1
    assert 'id="tenant-namespace-profile-mapping"' in partial
    assert "Namespace & Resource Profile Mapping" in partial
    assert "Pinned Snapshot" in partial
    assert "Profile ID:" in partial
    assert "Frozen Quota" in partial
    assert "item.historical" in partial
    assert "item.ownership_status" in partial
    assert "item.control_state" in partial
    assert "item.provider_uid" in partial
    assert "item.last_reconciled_at_label" in partial
    assert "No Namespace Allocations" in partial
    assert "components/states/_empty_state.html" in partial
    assert '<form' not in partial and "hx-post" not in partial
    assert detail.count('<form ') == 17


def test_mapping_preserves_five_row_limit_and_exact_tenant_boundary():
    context, registry = source(CONTEXT), source(REGISTRY)
    assert "get_tenant_namespace_profile_mapping_context(" in context
    assert "context['tenant_namespace_profile_mapping']" in context
    start = registry.index("def get_tenant_namespace_profile_mapping_context(")
    stop = registry.index("def get_namespace_registry_context(", start)
    mapping = registry[start:stop]
    assert "limit: int = 5" in mapping
    assert "if limit != 5:" in mapping
    assert ".filter(TenantEnvironment.tenant_id == tenant_id)" in mapping
    assert "joinedload(TenantNamespace.environment)" in mapping
    assert "joinedload(TenantNamespace.resource_profile)" in mapping
    assert ".limit(limit)" in mapping
    assert "TenantNamespace.created_at.desc()" in mapping
    assert "TenantNamespaceProvisioningStatus.RELEASED.value" in mapping
    assert "TenantNamespaceProvisioningStatus.DEPROVISIONED.value" in mapping
    assert "record.allocation_quota_json or {}" in mapping
    assert "_namespace_profile_version(record)" in mapping
    assert "allocation_control_state(record)" in mapping
    assert "runtime_adapter" not in mapping
    assert "core_api" not in mapping
    assert "db.session.commit" not in mapping


def test_committed_mapping_uses_shared_table_and_existing_registry_link():
    partial = source(PARTIAL)
    assert "operational_section_card.render(" in partial
    assert "section_intro.render(" in partial
    assert "table_ui.table_classes('min-w-[820px] lg:min-w-0 !table-fixed')" in partial
    assert 'class="w-full min-w-0 max-w-full overflow-x-auto"' in partial
    assert partial.count('scope="col"') == 4
    assert "w-[27%]" in partial and "w-[28%]" in partial
    assert "w-[20%]" in partial and "w-[25%]" in partial
    assert "item.quota.get('requests.cpu')" in partial
    assert "item.quota.get('requests.memory')" in partial
    assert "item.quota.get('limits.cpu')" in partial
    assert "item.quota.get('limits.memory')" in partial
    assert "item.quota.get('pods')" in partial
    assert "item.quota.get('requests.storage')" in partial
    assert "namespace_tenant_id=tenant.id" in partial
    assert "tenant.namespace_provisioning" in partial
    assert "No committed Namespace generation" in source(REGISTRY) or (
        "No committed Namespace generation" in partial
    )
    assert "not live Kubernetes" in partial
    assert "Release preserves verified resource values" in partial
