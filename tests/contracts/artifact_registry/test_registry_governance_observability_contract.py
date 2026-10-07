from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_registry_governance_is_committed_and_provider_neutral() -> None:
    models = (ROOT / 'app/models/registry.py').read_text()
    governance = (ROOT / 'app/artifact_registry/governance.py').read_text()
    harbor = (ROOT / 'app/integrations/registry/providers/harbor/governance.py').read_text()

    assert 'class RegistryGovernanceState' in models
    assert 'class RegistryProjectGovernance' in models
    assert 'class RegistryReplicationPolicy' in models
    assert 'HarborInstance' not in governance
    assert 'RegistryGovernanceCollector' in governance
    assert 'collect_harbor_governance' in harbor
    assert 'retention_status' in harbor
    assert 'immutability_status' in harbor
    assert 'ReplicationPolicyRecord' in harbor


def test_registry_metrics_reuses_canonical_metrics_source_binding() -> None:
    taxonomy = (ROOT / 'app/definitions/catalogs/integrations/taxonomy.yaml').read_text()
    metrics_contract = (
        ROOT / 'app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml'
    ).read_text()
    validators = (ROOT / 'app/integrations/observability/metrics_source/binding_validators/__init__.py').read_text()
    registry_validator = (
        ROOT / 'app/integrations/observability/metrics_source/binding_validators/registry_asset.py'
    ).read_text()

    assert 'asset_type: registry_instance' in taxonomy
    assert 'asset_type: registry_instance' in metrics_contract
    assert 'profile_key: registry-metrics-v1' in metrics_contract
    assert "register_binding_validator(PROMETHEUS_HTTP_ADAPTER, 'registry_instance'" in validators
    assert 'IntegrationBinding' in registry_validator
    assert 'RegistryHarborMetricsAuditor' in registry_validator


def test_artifact_registry_has_no_direct_prometheus_transport() -> None:
    for path in (ROOT / 'app/artifact_registry').glob('*.py'):
        content = path.read_text()
        assert 'requests.get(' not in content
        assert '/api/v1/query' not in content
        assert 'prometheus' not in content.lower() or path.name == 'observability.py'


def test_governance_workspace_keeps_independent_readiness_planes_out_of_posture() -> None:
    governance_presentation = (ROOT / 'app/artifact_registry/presentation_governance.py').read_text()
    template = (ROOT / 'app/templates/artifact_registry/governance.html').read_text()

    for label in (
        'Provider Readiness',
        'Inventory Readiness',
        'Metrics Readiness',
        'Webhook Readiness',
    ):
        assert label not in governance_presentation

    assert 'Governance Data Snapshot' in template
    assert "'policies', 'Policies'" in template
    assert "'replication', 'Replication'" in template
    assert 'Sync Governance' in template
    assert 'Webhook Admission' not in template
    assert 'Generate Token' not in template
    assert 'Registry reconciliation' not in template


def test_governance_sync_uses_registered_jobexecution_boundary() -> None:
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    adapter = (ROOT / 'app/artifact_registry/governance_job_adapter.py').read_text()

    assert "job_key='artifact_registry.governance.sync'" in routes
    assert 'build_registry_governance_sync_state' in adapter
    assert "GOVERNANCE_SYNC_JOB_TYPE = 'artifact_registry_governance'" in adapter
    assert 'get_or_create_job_policy(GOVERNANCE_SYNC_JOB_KEY)' in adapter
    assert 'def governance_sync_status(public_id: str)' in routes
    live_state = (ROOT / 'app/templates/artifact_registry/partials/_governance_sync_live_state.html').read_text()
    assert "url_for('artifact_registry.governance_sync_status'" in live_state
    assert 'hx-trigger="every 1s"' in live_state
    assert 'progress_bar.job_progress' in live_state
