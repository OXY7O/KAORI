from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

ADVANCED_CAPABILITIES = (
    'shared_global_quota',
    'resource_pools',
    'replication',
    'proxy',
    'tenant_cordon',
    'namespace_controls',
    'resource_rules',
    'cross_namespace_credential',
    'self_service_namespace',
)


def test_capsule_discovery_exposes_advanced_capabilities_without_native_emulation() -> None:
    source = (ROOT / 'app/kubernetes/tenant/capsule_provider.py').read_text(encoding='utf-8')

    for capability in ADVANCED_CAPABILITIES:
        assert f"'{capability}'" in source
    assert "probes.get('tenant_cordon')" in source
    assert "probes.get('namespace_controls')" in source
    assert "probes.get('resource_rules')" in source
    assert "probes.get('cross_namespace_credential')" in source
    assert "probes.get('self_service_namespace')" in source


def test_advanced_capsule_mutations_use_custom_objects_api_and_capability_gate() -> None:
    client = (
        ROOT
        / 'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/client.py'
    ).read_text(encoding='utf-8')
    source = (ROOT / 'app/kubernetes/tenant/capsule_advanced.py').read_text(encoding='utf-8')

    assert 'def custom_objects_api(' in client
    assert 'require_capsule_capability' in source
    assert 'create_cluster_custom_object' in source
    assert 'patch_cluster_custom_object' in source
    assert 'create_namespaced_custom_object' in source
    assert 'patch_namespaced_custom_object' in source
    assert 'delete_cluster_custom_object' in source
    assert 'delete_namespaced_custom_object' in source
    assert "provider_key != 'capsule'" in source
    assert 'native_kubernetes' not in source


def test_advanced_intent_is_committed_and_audited_without_secret_material() -> None:
    model = (ROOT / 'app/models/tenant_advanced.py').read_text(encoding='utf-8')
    service = (ROOT / 'app/kubernetes/tenant/capsule_advanced_service.py').read_text(encoding='utf-8')
    migration = (ROOT / 'migrations/versions/20260927_tenant_capsule_advanced.py').read_text(encoding='utf-8')

    assert 'class TenantAdvancedCapabilityIntent' in model
    assert 'desired_spec_json' in model
    assert 'effective_spec_json' in model
    assert 'reconciliation_evidence_json' in model
    assert 'tenant_advanced_capability_intents' in migration
    assert "target_type = 'tenant_advanced_capability'" in service
    assert "'secret_material_persisted': False" in service
    assert 'create_advanced_intent_committed' in service
    assert 'reconcile_advanced_intent_committed' in service
    assert 'remove_advanced_intent_committed' in service


def test_capsule_advanced_docs_preserve_single_authority_and_conditional_uat() -> None:
    docs = (ROOT / 'docs/architecture/kubernetes-tenant-capsule-advanced.md').read_text(encoding='utf-8')

    assert 'specific discovered capability' in docs
    assert 'fail closed' in docs
    assert 'single reconciliation authority' in docs
    assert 'Native mode does not emulate' in docs
    assert 'capability-conditional' in docs
    assert 'self-service namespace creation remains disabled' in docs
