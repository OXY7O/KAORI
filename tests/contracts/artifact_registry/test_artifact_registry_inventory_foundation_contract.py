from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_artifact_registry_uses_provider_neutral_digest_oriented_persistence() -> None:
    model = read('app/models/registry_artifact.py')
    migration = read('migrations/versions/20261003_artifact_registry_inventory.py')

    assert "class RegistryProject" in model
    assert "class RegistryRepository" in model
    assert "class RegistryArtifact" in model
    assert "class RegistryTag" in model
    assert "digest: Mapped[str]" in model
    assert "UniqueConstraint('repository_id', 'digest'" in model
    assert "HarborProject" not in model
    assert "HarborRepository" not in model
    assert "HarborArtifact" not in model
    assert "down_revision = '20261003_registry_harbor'" in migration


def test_artifact_registry_collection_is_worker_owned_and_read_only() -> None:
    provider = read('app/artifact_registry/inventory/providers.py')
    harbor = read('app/artifact_registry/inventory/harbor.py')
    sync = read('app/artifact_registry/inventory/sync.py')
    routes = read('app/artifact_registry/routes.py')
    presentation = read('app/artifact_registry/inventory/presentation.py')
    client = read('app/integrations/registry/providers/harbor/client.py')

    assert "if instance.provider_key == 'harbor'" in provider
    assert "collect_harbor_inventory" in harbor
    assert "commit_registry_inventory" in sync
    assert "with_for_update()" in sync
    assert "db.session.commit()" in sync
    assert "provider discovery returned zero projects" in sync
    assert "build_client" not in routes
    assert "HarborClient" not in routes
    assert "build_client" not in presentation
    assert "HarborClient" not in presentation
    assert "requests.post(" not in client
    assert "requests.put(" not in client
    assert "requests.patch(" not in client
    assert "requests.delete(" not in client


def test_artifact_registry_is_registered_as_first_class_workspace_with_canonical_blocker() -> None:
    catalog = read('app/common/workspace_navigation_catalog.py')
    navigation = read('app/common/workspace_navigation.py')
    breadcrumb = read('app/common/navigation.py')
    overview = read('app/templates/artifact_registry/overview.html')
    inventory = read('app/templates/artifact_registry/inventory.html')

    assert "key='artifact_registry'" in catalog
    assert "'artifact_registry_inventory': (" in catalog
    assert "'projects', 'Projects'" in catalog
    assert "'repositories', 'Repositories'" in catalog
    assert "'artifacts', 'Artifacts'" in catalog
    assert "return 'artifact_registry'" in navigation
    assert "BreadcrumbItem('Artifact Registry', 'package-search')" in breadcrumb
    assert 'components/provider_prerequisite/_setup_blocker.html' in overview
    assert 'components/provider_prerequisite/_hero_context.html' in overview
    assert 'components/provider_prerequisite/_setup_blocker.html' in inventory
    assert "url_for('integrations.registry')" in overview
    assert "url_for('integrations.registry')" in inventory


def test_artifact_registry_sync_is_canonical_job_execution_with_inventory_queue() -> None:
    definitions = read('app/definitions/catalogs/platform_operations/jobs/registered_jobs.yaml')
    jobs = read('app/artifact_registry/inventory/sync_jobs.py')
    adapter = read('app/artifact_registry/inventory/job_adapter.py')
    tasks = read('app/artifact_registry/inventory/tasks.py')
    config = read('app/config/default.py')

    assert 'key: artifact_registry.inventory.sync' in definitions
    assert 'domain_execute_permission: artifact_registry.sync' in definitions
    assert 'queue_name: inventory' in definitions
    assert 'enqueue_canonical_job(' in jobs
    assert "job_type='artifact_registry_inventory'" in jobs
    assert "'eligible_target_count': eligible_count" in adapter
    assert "present_job_execution(active)" in adapter
    assert "name='app.artifact_registry.inventory.tasks.sync_artifact_registry_inventory'" in tasks
    assert "context.fail(" in tasks
    assert "'app.artifact_registry.inventory.tasks'" in config
    assert "'app.artifact_registry.inventory.tasks.sync_artifact_registry_inventory'" in config


def test_artifact_registry_rbac_catalog_matches_migration_and_job_dependency() -> None:
    import yaml

    access = yaml.safe_load(read('app/definitions/catalogs/access/rbac/access.yaml'))
    migration = read('migrations/versions/20261003_artifact_registry_inventory.py')

    permissions = {item['key']: item for item in access['permissions']}
    grants = {item['key']: set(item['permissions']) for item in access['system_roles']}

    assert permissions['artifact_registry.view']['module'] == 'artifact_registry'
    assert permissions['artifact_registry.sync']['module'] == 'artifact_registry'
    assert set(access['permission_dependencies']['artifact_registry.sync']) == {
        'artifact_registry.view',
        'jobs.execute',
    }
    for role in ('viewer', 'operator', 'editor', 'admin', 'auditor'):
        assert 'artifact_registry.view' in grants[role]
    for role in ('operator', 'editor', 'admin'):
        assert 'artifact_registry.sync' in grants[role]
    assert "('viewer', 'operator', 'editor', 'admin', 'auditor')" in migration
    assert "('operator', 'editor', 'admin')" in migration
