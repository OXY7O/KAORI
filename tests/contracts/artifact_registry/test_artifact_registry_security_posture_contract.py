from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_registry_security_models_are_provider_neutral_and_digest_attached() -> None:
    model = read('app/models/registry_security.py')
    migration = read('migrations/versions/20261004_artifact_registry_security.py')

    assert 'class RegistrySecurityCollectionState' in model
    assert 'class RegistryArtifactSecuritySnapshot' in model
    assert 'class RegistryVulnerabilityFinding' in model
    assert "ForeignKey('registry_artifacts.id'" in model
    assert "UniqueConstraint('artifact_id'" in model
    assert 'HarborSecuritySnapshot' not in model
    assert 'TrivyFinding' not in model
    assert "down_revision = '20261003_artifact_registry_inv'" in migration


def test_harbor_security_collector_is_read_only_and_does_not_claim_trust_evaluation() -> None:
    client = read('app/integrations/registry/providers/harbor/client.py')
    collector = read('app/artifact_registry/security/harbor.py')
    sync = read('app/artifact_registry/security/sync.py')

    assert 'get_artifact(' in client
    assert 'get_artifact_addition(' in client
    for mutation in ('requests.post(', 'requests.put(', 'requests.patch(', 'requests.delete('):
        assert mutation not in client
    assert "trust_state='not_evaluated'" in collector
    assert "'supported_observed'" in collector
    assert "'supported_unavailable'" in collector
    assert 'scan.trigger' not in collector
    assert 'commit_registry_security' in sync
    assert 'db.session.commit()' in sync


def test_registry_security_workspace_exposes_provider_capability_gaps_without_fabrication() -> None:
    presentation = read('app/artifact_registry/security/presentation.py')
    template = read('app/templates/artifact_registry/security.html')
    catalog = read('app/common/workspace_navigation_catalog.py')
    navigation = read('app/common/workspace_navigation.py')

    for state in ('supported_observed', 'supported_unavailable', 'unsupported', 'not_collected'):
        assert state in presentation
    assert 'Provider Capability Matrix' in template
    assert 'Presence is not trust-policy evaluation.' in template
    assert 'not automatically promoted into Alert Intelligence' in template
    assert "'artifact_registry_security': (" in catalog
    assert "'Vulnerabilities'" in catalog
    assert "'Supply Chain'" in catalog
    assert "return 'artifact_registry_security'" in navigation


def test_registry_security_collection_requires_committed_inventory_and_canonical_job_execution() -> None:
    targets = read('app/artifact_registry/security/sync_jobs.py')
    tasks = read('app/artifact_registry/security/tasks.py')
    definitions = read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml')
    config = read('app/config/default.py')
    job_presentation = read('app/platform_operations/jobs/configuration.py')

    assert 'RegistryCollectionState' in targets
    assert "inventory_states[item.id].status == 'collected'" in targets
    assert 'enqueue_canonical_job(' in targets
    assert "job_type='artifact_registry_security'" in targets
    assert "resource_group='artifact-registry-security:global'" in targets
    assert "name='app.artifact_registry.security.tasks.sync_artifact_registry_security'" in tasks
    assert 'context.fail(' in tasks
    assert 'key: artifact_registry.security.sync' in definitions
    assert 'domain_execute_permission: artifact_registry.sync' in definitions
    assert "'app.artifact_registry.security.tasks.sync_artifact_registry_security'" in config
    assert "'artifact_registry.security.sync': {" in job_presentation


def test_harbor_full_validation_keeps_optional_security_evidence_outside_core_readiness() -> None:
    validation = read('app/integrations/registry/providers/harbor/validation.py')
    contract = read('app/definitions/catalogs/integrations/registry/contract.yaml')

    assert "'optional_capabilities_observed'" in validation
    assert "'required_capabilities_observed'" in validation
    assert "capabilities.add('vulnerability_read')" in validation
    assert "capabilities.add('signature_metadata')" in validation
    assert "capabilities.add('sbom_metadata')" in validation
    assert '- key: vulnerability_read' in contract
    assert '- key: signature_metadata' in contract
    assert '- key: sbom_metadata' in contract


def test_registry_security_findings_remain_evidence_not_alert_fanout() -> None:
    routes = read('app/artifact_registry/routes.py')
    tasks = read('app/artifact_registry/security/tasks.py')
    template = read('app/templates/artifact_registry/security.html')

    assert 'AlertSignal' not in routes
    assert 'AlertSignal' not in tasks
    assert 'create_alert' not in routes
    assert 'create_alert' not in tasks
    assert 'not automatically promoted into Alert Intelligence' in template
