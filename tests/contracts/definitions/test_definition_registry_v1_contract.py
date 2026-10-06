from pathlib import Path

import yaml

ROOT = Path('.')
CATALOG_ROOT = ROOT / 'app/definitions/catalogs'


def load(path: str) -> dict:
    return yaml.safe_load((CATALOG_ROOT / path).read_text())


def test_definition_registry_has_versioned_yaml_for_growing_system_catalogs():
    expected = {
        'intelligence/rules.yaml': 'intelligence_rules',
        'access/rbac/access.yaml': 'rbac_access',
        'intelligence/knowledge/system_runbooks.yaml': 'system_runbooks',
        'intelligence/automation/production_readiness.yaml': 'automation_production_readiness',
        'access/authentication/identity_provider/providers.yaml': 'identity_providers',
        'platform_operations/jobs/registered_jobs.yaml': 'registered_jobs',
        'kubernetes/analytics/datasets.yaml': 'kubernetes_analytics_datasets',
        'reports/catalog.yaml': 'report_catalog',
        'reports/coverage.yaml': 'report_coverage_catalog',
        'platform_operations/notifications/event_categories.yaml': 'notification_event_categories',
        'integrations/taxonomy.yaml': 'integration_taxonomy',
        'integrations/compatibility.yaml': 'integration_compatibility',
        'integrations/orchestration/container_orchestrator/providers/kubernetes.yaml': 'integration_provider_contract',
        'integrations/observability/metrics_source/contract.yaml': 'integration_provider_contract',
        'integrations/observability/alert_source/providers/alertmanager.yaml': 'integration_provider_contract',
        'integrations/storage/object_storage/contract.yaml': 'integration_provider_contract',
    }
    for relative, kind in expected.items():
        document = load(relative)
        assert document['schema_version'] == 1
        assert document['kind'] == kind


def test_runtime_modules_consume_registry_instead_of_embedding_catalog_growth():
    modules = [
        'app/intelligence/catalog.py',
        'app/access/rbac/defaults.py',
        'app/intelligence/knowledge/system_catalog.py',
        'app/intelligence/resolver/production_readiness.py',
        'app/access/authentication/identity_provider/catalog.py',
        'app/platform_operations/jobs/definition_catalog.py',
        'app/kubernetes/analytics/materialization/catalog.py',
        'app/reports/catalog.py',
        'app/platform_operations/notifications/event_catalog.py',
        'app/integrations/taxonomy.py',
        'app/integrations/compatibility.py',
        'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/capabilities.py',
        'app/integrations/observability/metrics_source/capabilities.py',
        'app/integrations/observability/metrics_source/binding_profiles.py',
        'app/integrations/observability/alert_source/providers/alertmanager/capabilities.py',
        'app/integrations/observability/alert_source/providers/alertmanager/binding_profiles.py',
        'app/integrations/storage/object_storage/providers/minio/capabilities.py',
        'app/integrations/storage/object_storage/providers/minio/compatibility.py',
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
    access = load('access/rbac/access.yaml')
    jobs = load('platform_operations/jobs/registered_jobs.yaml')
    permission_keys = {item['key'] for item in access['permissions']}
    for role in access['system_roles']:
        assert set(role['permissions']) <= permission_keys
    for job in jobs['jobs']:
        assert job['configure_permission'] in permission_keys
        assert job['execute_permission'] in permission_keys
        if job.get('domain_execute_permission'):
            assert job['domain_execute_permission'] in permission_keys


def test_integration_definitions_are_taxonomy_policy_contract_and_qualification_driven():
    taxonomy = load('integrations/taxonomy.yaml')
    compatibility = load('integrations/compatibility.yaml')
    kubernetes = load('integrations/orchestration/container_orchestrator/providers/kubernetes.yaml')
    metrics_source = load('integrations/observability/metrics_source/contract.yaml')
    alertmanager = load('integrations/observability/alert_source/providers/alertmanager.yaml')
    object_storage = load('integrations/storage/object_storage/contract.yaml')

    domain_keys = {item['key'] for item in taxonomy['domains']}
    assert domain_keys == {'orchestration', 'observability', 'storage'}
    assert {item['asset_type'] for item in taxonomy['consumer_assets']} >= {
        'kubernetes_cluster',
        'object_storage_system',
    }

    lifecycle = compatibility['lifecycle_policy']
    assert lifecycle['policy_year'] == 2026
    assert lifecycle['lookback_years'] == 5
    assert lifecycle['anchor_year'] == lifecycle['policy_year'] - lifecycle['lookback_years']
    assert lifecycle['renewal_cadence'] == 'annual'

    posture_keys = {item['key'] for item in compatibility['support_postures']}
    assert {'current', 'extended_supported', 'end_of_life', 'unverified'} <= posture_keys

    contracts = {item['key']: item for item in compatibility['contract_profiles']}
    assert {
        'kubernetes-core-v1',
        'prometheus-http-core-v1',
        'alertmanager-api-v2-contract-v1',
    } <= set(contracts)

    products = {item['key']: item for item in compatibility['products']}
    assert set(products) == {'kubernetes', 'prometheus', 'alertmanager', 'thanos'}
    assert all(item['selection_mode'] == 'automatic_detected_version' for item in products.values())
    assert all(item['version_source'] for item in products.values())
    assert all(item['contract_profile'] in contracts for item in products.values())

    qualifications = compatibility['qualifications']
    assert {item['product'] for item in qualifications} == set(products)
    assert all(item['contract_profile'] in contracts for item in qualifications)
    assert all(item['support_level'] in posture_keys for item in qualifications)

    assert set(kubernetes['compatibility_profiles']) == {'kubernetes-core-v1'}
    assert set(metrics_source['compatibility_profiles']) == {'prometheus-http-core-v1'}
    assert set(alertmanager['compatibility_profiles']) == {'alertmanager-api-v2-contract-v1'}
    assert {item['key'] for item in alertmanager['profiles']} == {
        item['key'] for item in qualifications if item['product'] == 'alertmanager'
    }

    assert {item['profile_key'] for item in metrics_source['binding_profiles']} == {
        'kubernetes-metrics-v1',
        'object-storage-metrics-v1',
    }
    assert {item['profile_key'] for item in alertmanager['consumer_profiles']} >= {
        'kubernetes-alerts-v1',
        'object-storage-alerts-v1',
        'global-alerts-v1',
    }

    assert object_storage['capability_profile'] == 's3-object-storage-v1'
    minio_profiles = [
        profile
        for product in object_storage['products']
        if product['key'] == 'minio'
        for profile in product['compatibility_profiles']
    ]
    assert {profile['key'] for profile in minio_profiles} == {'minio-community-policy-v1'}
    assert all(profile['contract_profile'] == object_storage['capability_profile'] for profile in minio_profiles)
    assert all(profile['support_level'] in posture_keys for profile in minio_profiles)


def test_integration_taxonomy_exposes_ordered_runtime_collections():
    source = Path('app/integrations/taxonomy.py').read_text()
    assert 'def ordered_domain_definitions()' in source
    assert 'def ordered_capability_definitions()' in source
    assert 'get_domain_definition(item.domain_key).order' in source
