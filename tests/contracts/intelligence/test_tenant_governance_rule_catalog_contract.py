from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

TENANT_RULE_KEYS = (
    'kubernetes.tenant.credential.renewal_due',
    'kubernetes.tenant.credential.inactive_owner_active_access',
    'kubernetes.tenant.credential.revoked_still_usable',
    'kubernetes.tenant.access.grant_drift',
    'kubernetes.tenant.access.unmanaged_principal',
    'kubernetes.tenant.namespace.profile_drift',
    'kubernetes.tenant.namespace.missing_tenant_admin',
    'kubernetes.tenant.policy.exposure_violation',
    'kubernetes.tenant.policy.managed_resource_drift',
    'kubernetes.tenant.provider.degraded',
    'kubernetes.tenant.provider.native_recovery',
    'kubernetes.tenant.production.human_mutation',
    'kubernetes.tenant.production.deployment_outside_cicd',
    'kubernetes.tenant.capacity.near_capacity',
    'kubernetes.tenant.capacity.exhausted',
    'kubernetes.tenant.capacity.overcommitted',
    'kubernetes.tenant.capacity.allocation_denied',
    'kubernetes.tenant.capacity.evidence_unknown',
)


def test_tenant_governance_rules_are_canonical_catalog_entries() -> None:
    catalog = (ROOT / 'app/definitions/catalogs/intelligence/rules.yaml').read_text(encoding='utf-8')

    for rule_key in TENANT_RULE_KEYS:
        assert f'rule_key: {rule_key}' in catalog
    assert 'rule_key: native_kubernetes.tenant.' not in catalog
    assert 'rule_key: capsule.tenant.' not in catalog
    assert 'source_kind: tenant_' not in catalog
    assert 'signal_source: kaori_tenant_' not in catalog
    assert 'signal_source: kaori_kubernetes_analysis' in catalog


def test_tenant_governance_uses_existing_intelligence_engine_and_exception_authority() -> None:
    service = (ROOT / 'app/intelligence/service.py').read_text(encoding='utf-8')
    evaluator = (ROOT / 'app/intelligence/tenant_governance_recommendations.py').read_text(encoding='utf-8')

    assert 'build_tenant_governance_recommendation_findings' in service
    assert 'build_tenant_governance_recommendation_findings(rules)' in service
    assert 'RuleException' not in evaluator
    assert 'runtime_adapter' not in evaluator
    assert 'requests.' not in evaluator


def test_evaluator_consumes_canonical_committed_tenant_evidence() -> None:
    evaluator = (ROOT / 'app/intelligence/tenant_governance_recommendations.py').read_text(encoding='utf-8')

    for model_name in (
        'Tenant',
        'TenantAccessGrant',
        'TenantCapacityDecision',
        'TenantCredential',
        'TenantMembership',
        'TenantNamespace',
        'TenantManagedResourceIntent',
        'TenantAuditEvidence',
        'AuditEvent',
    ):
        assert model_name in evaluator
    assert 'provider_evidence_json' in evaluator
    assert 'correlation_status' in evaluator
    assert 'capacity_state' in evaluator


def test_tenant_governance_architecture_preserves_evidence_provenance() -> None:
    docs = (ROOT / 'docs/architecture/kubernetes-tenant-governance-intelligence.md').read_text(encoding='utf-8')

    assert 'canonical Intelligence engine' in docs
    assert 'committed Tenant evidence' in docs
    assert 'provider-neutral' in docs
    assert 'accepted-risk' in docs
    assert 'does not recompute' in docs
    assert 'live provider request' in docs
