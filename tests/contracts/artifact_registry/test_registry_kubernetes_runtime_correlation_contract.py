from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_runtime_correlation_is_committed_and_provider_neutral() -> None:
    model = read('app/models/registry_correlation.py')
    materialize = read('app/artifact_registry/correlation/materialize.py')
    migration = read('migrations/versions/20261004_registry_kubernetes_correlation.py')

    assert 'class RegistryWorkloadBinding' in model
    assert 'class RegistryCorrelationState' in model
    assert "ForeignKey('registry_artifacts.id'" in model
    assert "ForeignKey('pod_inventory.id'" in model
    assert "match_type: Mapped[str]" in model
    assert "confidence: Mapped[str]" in model
    assert 'HarborWorkloadBinding' not in model
    assert "down_revision = '20261004_artifact_registry_sec'" in migration
    assert 'filter_current_generation' in materialize
    assert 'RegistryWorkloadBinding.query.delete' in materialize
    assert 'build_client' not in materialize
    assert 'kubernetes.client' not in materialize


def test_runtime_correlation_is_digest_first_and_never_promotes_tag_to_digest_certainty() -> None:
    materialize = read('app/artifact_registry/correlation/materialize.py')
    template = read('app/templates/artifact_registry/runtime_usage.html')

    assert "'digest', 'authoritative'" in materialize
    assert "'tag_reference', 'weak'" in materialize
    assert "'ambiguous_digest', 'none'" in materialize
    assert "'ambiguous_tag', 'none'" in materialize
    assert 'candidate_count' in materialize
    assert 'Tag-only matches are retained as weaker evidence' in template
    assert 'Mutable tag evidence; do not treat as digest certainty.' in template


def test_runtime_correlation_preserves_both_registry_and_kubernetes_provenance() -> None:
    model = read('app/models/registry_correlation.py')
    materialize = read('app/artifact_registry/correlation/materialize.py')

    for field in (
        'registry_source_id',
        'registry_provider_key',
        'registry_observed_at',
        'kubernetes_observed_at',
        'image_reference',
        'image_id',
    ):
        assert field in model
        assert field in materialize
    assert "'correlation_boundary': 'committed_registry_and_kubernetes_inventory'" in materialize


def test_runtime_usage_has_cross_domain_permission_and_security_navigation() -> None:
    access = yaml.safe_load(read('app/definitions/catalogs/access/rbac/access.yaml'))
    catalog = read('app/common/workspace_navigation_catalog.py')
    routes = read('app/artifact_registry/routes.py')

    permissions = {item['key']: item for item in access['permissions']}
    grants = {item['key']: set(item['permissions']) for item in access['system_roles']}

    assert permissions['artifact_registry.runtime_correlation.view']['module'] == 'artifact_registry'
    assert set(access['permission_dependencies']['artifact_registry.runtime_correlation.view']) == {
        'artifact_registry.view',
        'inventory.view',
    }
    for role in ('viewer', 'operator', 'editor', 'admin', 'auditor'):
        assert 'artifact_registry.runtime_correlation.view' in grants[role]

    assert "'runtime_usage'" in catalog
    assert "'artifact_registry.runtime_correlation.view'" in catalog
    assert "@permission_required('artifact_registry.runtime_correlation.view')" in routes


def test_runtime_correlation_uses_canonical_job_execution_and_inventory_queue() -> None:
    jobs = read('app/artifact_registry/correlation/sync_jobs.py')
    task = read('app/artifact_registry/correlation/tasks.py')
    definitions = read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml')
    config = read('app/config/default.py')

    assert 'enqueue_canonical_job(' in jobs
    assert 'filter_current_generation(PodInventory.query, PodInventory).count()' in jobs
    assert "job_type='artifact_registry_runtime_correlation'" in jobs
    assert "queue_name=INVENTORY_QUEUE" in jobs
    assert "resource_group='artifact-registry-runtime-correlation:global'" in jobs
    assert "name='app.artifact_registry.correlation.tasks.materialize_artifact_registry_runtime_correlation'" in task
    assert 'key: artifact_registry.runtime_correlation.materialize' in definitions
    assert 'domain_execute_permission: artifact_registry.sync' in definitions
    assert "'app.artifact_registry.correlation.tasks.materialize_artifact_registry_runtime_correlation'" in config


def test_vulnerability_rows_link_to_artifact_scoped_runtime_blast_radius() -> None:
    presentation = read('app/artifact_registry/security/presentation.py')
    template = read('app/templates/artifact_registry/security.html')
    runtime_template = read('app/templates/artifact_registry/runtime_usage.html')

    assert "'artifact_id': artifact.id" in presentation
    assert "url_for('artifact_registry.security_runtime_usage', artifact_id=row.artifact_id)" in template
    assert 'Artifact-scoped blast radius' in runtime_template
