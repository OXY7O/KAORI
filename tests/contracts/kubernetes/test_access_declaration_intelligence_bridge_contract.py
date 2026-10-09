from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_access_drift_reuses_existing_intelligence_rule_and_committed_evidence() -> None:
    service = read('app/intelligence/tenant_governance_recommendations.py')
    native = read('app/kubernetes/tenant/access_drift_analysis.py')
    rules = read('app/definitions/catalogs/intelligence/rules.yaml')

    assert 'def _access_declaration_findings(' in service
    assert 'def access_declaration_rule_key(' in service
    assert "'kubernetes.tenant.access.grant_drift'" in service
    assert 'kubernetes.tenant.access.grant_drift' in rules
    assert 'kubernetes_tenant_access_drift_evidence' in service
    assert 'kubernetes_tenant_native_access_drift_evidence' in service
    assert 'AuditEvent.query.filter(' in service
    assert '_ACCESS_DECLARATION_MAX_AGE_SECONDS = 3600' in service
    assert "'effective_rbac_verified'" in service
    assert "'provider_mutation_performed': False" in service
    assert '*_access_declaration_findings(rules)' in service
    assert 'def evaluate_native_access_drift_committed(' in native
    assert 'def evaluate_tenant_access_drift_committed(' in native

    # External subject ownership without a correlated Grant cannot be
    # elevated into the runtime-audit-only unmanaged-principal Intelligence rule.
    for foreign_code in (
        'external_capsule_owner', 'external_native_rolebinding',
        'unverified_kaori_grant_marker',
    ):
        assert foreign_code not in service
    assert "return 'kubernetes.tenant.access.grant_drift'" in service
    assert "'kubernetes.tenant.access.unmanaged_principal'" not in (
        service.split('def access_declaration_rule_key(', 1)[1]
        .split('def _access_declaration_findings(', 1)[0]
    )
