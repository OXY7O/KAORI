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
    assert "Committed Quota Snapshot" in partial
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
    assert "_committed_profile_history(tenant, records)" in mapping
    assert "_namespace_profile_version(record)" in mapping
    assert "allocation_control_state(record)" in mapping
    assert "runtime_adapter" not in mapping
    assert "core_api" not in mapping
    assert "db.session.commit" not in mapping


def test_committed_mapping_uses_per_namespace_cards_and_existing_registry_link():
    partial = source(PARTIAL)
    assert "operational_section_card.render(" in partial
    assert "section_intro.render(" in partial
    assert 'aria-label="Namespace allocation cards"' in partial
    assert 'grid-cols-1 gap-4 xl:grid-cols-2' in partial
    assert "<article " in partial
    assert "<table" not in partial and "overflow-x-auto" not in partial
    assert "item.namespace" in partial
    assert "item.profile_public_id" in partial
    assert "item.profile_version" in partial
    assert "item.ownership_status" in partial
    assert "item.control_state" in partial
    assert "item.last_reconciled_at_label" in partial
    assert "item.quota.get('requests.cpu')" in partial
    assert "item.quota.get('requests.memory')" in partial
    assert "item.quota.get('limits.cpu')" in partial
    assert "item.quota.get('limits.memory')" in partial
    assert "item.quota.get('pods')" in partial
    assert "item.quota.get('requests.storage')" in partial
    assert "namespace_tenant_id=tenant.id" in partial
    assert "tenant.namespace_provisioning" in partial
    assert "No committed Namespace generation" in partial
    assert "not live Kubernetes utilization" in partial
    assert "Native Release preserves verified quotas" in partial
    assert "components/states/_empty_state.html" in partial


def test_release_history_is_verified_optional_disclosure_not_name_matching():
    partial, registry = source(PARTIAL), source(REGISTRY)
    assert "<details " in partial
    assert "item.verified_history" in partial
    assert "Lifecycle History" in partial
    assert "verified predecessor(s)" in partial
    assert "previous.tenant_generation" in partial
    assert "previous.namespace_generation" in partial
    assert "previous.quota.get('requests.cpu')" in partial
    assert "previous.quota.get('requests.memory')" in partial
    assert "No verified cross-Tenant Release lineage" in partial

    assert "def _verified_native_profile_predecessors(" in registry
    assert "lineage.get('predecessor_tenant_id')" in registry
    assert "lineage.get('predecessor_generation')" in registry
    assert "lineage.get('predecessor_correlation_id')" in registry
    assert "lineage.get('provider_uid_verified') is not True" in registry
    assert "prior.lifecycle_status == TenantLifecycleStatus.RELEASED.value" in registry
    assert "prior.cluster_id == tenant.cluster_id" in registry
    assert "prior.slug == tenant.slug" in registry
    assert "evidence.get('provider_uid') == prior_evidence.get('provider_uid')" in registry
    assert "def _matches_verified_native_profile_predecessor(" in registry
    assert "TenantNamespace.provider_reference.in_(uids)" in registry
    assert "TenantNamespace.provisioning_status" in registry
    assert "TenantNamespaceProvisioningStatus.RELEASED.value" in registry
    assert ".limit(75)" in registry
    assert "'verified_history': history_by_provider.get(" in registry
    assert "runtime_adapter" not in registry[registry.index("def _verified_native_profile_predecessors("):registry.index("def get_namespace_registry_context(")]
