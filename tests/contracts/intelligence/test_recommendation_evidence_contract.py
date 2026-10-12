from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_recommendation_current_facts_are_source_qualified() -> None:
    service = source('app/intelligence/service.py')
    storage = source('app/intelligence/object_storage_recommendations.py')
    tenant = source('app/intelligence/tenant_governance_recommendations.py')
    assert 'TLSCertificateCollectionState.secret_collection_status == TLS_COLLECTION_COLLECTED' in service
    assert 'TLSCertificateInventory.collected_at >= cutoff' in service
    assert 'ObjectStorageSystem.inventory_observed_at >= cutoff' in storage
    assert 'if observed < cutoff:' in storage
    assert "IntegrationInstance.enabled.is_(True)" in storage
    assert 'db.session.rollback()' in service
    assert 'evidence_issues.append(label)' in service
    assert '*_audit_findings(rules),' not in tenant
    assert '*_policy_event_findings(rules),' not in tenant
