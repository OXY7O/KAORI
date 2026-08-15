from pathlib import Path

import yaml

ROOT = Path('.')
CATALOG_ROOT = ROOT / 'app/definitions/catalogs'


def load(path: str) -> dict:
    return yaml.safe_load((CATALOG_ROOT / path).read_text())


def test_definition_registry_has_versioned_yaml_for_growing_system_catalogs():
    expected = {
        'intelligence/rules.yaml': 'intelligence_rules',
        'rbac/access.yaml': 'rbac_access',
        'knowledge/system_runbooks.yaml': 'system_runbooks',
        'automation/production_readiness.yaml': 'automation_production_readiness',
        'auth/providers.yaml': 'auth_providers',
        'jobs/registered_jobs.yaml': 'registered_jobs',
        'analytics/kubernetes_datasets.yaml': 'kubernetes_analytics_datasets',
        'reports/catalog.yaml': 'report_catalog',
        'notifications/event_categories.yaml': 'notification_event_categories',
    }
    for relative, kind in expected.items():
        document = load(relative)
        assert document['schema_version'] == 1
        assert document['kind'] == kind


def test_runtime_modules_consume_registry_instead_of_embedding_catalog_growth():
    modules = [
        'app/intelligence/catalog.py',
        'app/rbac/defaults.py',
        'app/knowledge/system_catalog.py',
        'app/resolver/production_readiness.py',
        'app/auth/providers/catalog.py',
        'app/jobs/definition_catalog.py',
        'app/analytics/kubernetes/materialization/catalog.py',
        'app/reports/catalog.py',
        'app/notifications/event_catalog.py',
    ]
    content = '\n'.join(Path(path).read_text() for path in modules)
    assert 'load_definition_document' in content
    assert 'yaml.safe_load' not in content
    assert 'yaml.load' not in content


def test_definition_loader_rejects_duplicate_keys_and_unknown_schema_versions():
    loader = Path('app/definitions/loader.py').read_text()
    assert 'Duplicate YAML key is not allowed' in loader
    assert 'schema_version' in loader
    assert 'Unsupported schema_version' in loader


def test_rbac_and_jobs_reference_canonical_permissions():
    access = load('rbac/access.yaml')
    jobs = load('jobs/registered_jobs.yaml')
    permission_keys = {item['key'] for item in access['permissions']}
    for role in access['system_roles']:
        assert set(role['permissions']) <= permission_keys
    for job in jobs['jobs']:
        assert job['configure_permission'] in permission_keys
        assert job['execute_permission'] in permission_keys
        if job.get('domain_execute_permission'):
            assert job['domain_execute_permission'] in permission_keys
