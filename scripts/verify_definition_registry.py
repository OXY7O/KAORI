#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = ROOT / 'app' / 'definitions' / 'catalogs'

EXPECTED = {
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


class StrictLoader(yaml.SafeLoader):
    pass


def _mapping(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f'duplicate YAML key: {key!r}')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load(relative: str) -> dict:
    path = CATALOG_ROOT / relative
    loader = StrictLoader(path.read_text(encoding='utf-8'))
    try:
        data = loader.get_single_data()
    finally:
        loader.dispose()
    if not isinstance(data, dict):
        raise ValueError(f'{relative}: root must be mapping')
    if data.get('schema_version') != 1:
        raise ValueError(f'{relative}: schema_version must be 1')
    if data.get('kind') != EXPECTED[relative]:
        raise ValueError(f'{relative}: kind must be {EXPECTED[relative]!r}')
    return data


def unique(items: list[dict], key: str, label: str) -> set[str]:
    values = [str(item.get(key) or '').strip() for item in items]
    if any(not value for value in values):
        raise ValueError(f'{label}: {key} must not be empty')
    if len(values) != len(set(values)):
        raise ValueError(f'{label}: duplicate {key}')
    return set(values)


def main() -> int:
    try:
        docs = {relative: load(relative) for relative in EXPECTED}

        rules = docs['intelligence/rules.yaml']['rules']
        unique(rules, 'rule_key', 'intelligence rules')

        access = docs['access/rbac/access.yaml']
        permission_keys = unique(access['permissions'], 'key', 'permissions')
        unique(access['system_roles'], 'key', 'system roles')
        for role in access['system_roles']:
            unknown = sorted(set(role.get('permissions') or ()) - permission_keys)
            if unknown:
                raise ValueError(f'role {role["key"]} references unknown permissions: {", ".join(unknown)}')

        jobs = docs['platform_operations/jobs/registered_jobs.yaml']['jobs']
        unique(jobs, 'key', 'registered jobs')
        unique(jobs, 'operation', 'registered jobs')
        for job in jobs:
            for field in ('configure_permission', 'execute_permission', 'domain_execute_permission'):
                value = str(job.get(field) or '').strip()
                if value and value not in permission_keys:
                    raise ValueError(f'job {job["key"]} references unknown permission {value!r}')
            for field in ('dispatcher_path', 'context_builder_path'):
                value = str(job.get(field) or '')
                if ':' not in value:
                    raise ValueError(f'job {job["key"]} has invalid {field}')

        runbooks = docs['intelligence/knowledge/system_runbooks.yaml']['runbooks']
        unique(runbooks, 'runbook_key', 'system runbooks')
        for runbook in runbooks:
            if runbook.get('approval_policy') == 'allowed' and not runbook.get('recovery'):
                raise ValueError(f'runbook {runbook["runbook_key"]} cannot auto-allow without recovery metadata')

        readiness = docs['intelligence/automation/production_readiness.yaml']
        checks = readiness.get('required_checks') or []
        stages = readiness.get('rollout_stages') or []
        if len(checks) != len(set(checks)) or len(stages) != len(set(stages)):
            raise ValueError('automation readiness checks/stages must be unique')
        if not stages or stages[0] != 'disabled' or stages[-1] != 'production':
            raise ValueError('automation rollout must start disabled and end production')

        providers = docs['access/authentication/identity_provider/providers.yaml']['providers']
        unique(providers, 'provider_key', 'identity providers')

        analytics = docs['kubernetes/analytics/datasets.yaml']
        datasets = list(analytics['datasets']) + [analytics['forecast_dataset']]
        unique(datasets, 'key', 'analytics datasets')
        for dataset in datasets:
            if ':' not in str(dataset.get('builder_path') or ''):
                raise ValueError(f'dataset {dataset["key"]} has invalid builder_path')

        reports = docs['reports/catalog.yaml']
        formats = unique(reports['output_formats'], 'value', 'report formats')
        unique(reports['report_types'], 'value', 'report types')
        for report in reports['report_types']:
            allowed = set(report.get('allowed_formats') or ())
            if report.get('default_format') not in allowed or not allowed <= formats:
                raise ValueError(f'report {report["value"]} has invalid format contract')

        report_coverage = docs['reports/coverage.yaml']
        coverage_domains = unique(report_coverage['domains'], 'key', 'report coverage domains')
        allowed_coverage_statuses = {'Published', 'Evidence Ready', 'Planned', 'Reserved'}
        for domain in report_coverage['domains']:
            if domain.get('status') not in allowed_coverage_statuses:
                raise ValueError(f'report coverage {domain["key"]} has unsupported status')
            unique(domain.get('items') or [], 'name', f'report coverage {domain["key"]} items')
        if 'object_storage' not in coverage_domains:
            raise ValueError('Object Storage report coverage domain is missing')
        object_storage = next(domain for domain in report_coverage['domains'] if domain['key'] == 'object_storage')
        if object_storage.get('status') != 'Published':
            raise ValueError(
                'Object Storage report coverage must be Published after canonical contracts are registered'
            )

        notifications = docs['platform_operations/notifications/event_categories.yaml']
        category_keys = set(notifications['categories'])
        if notifications.get('default_category') not in category_keys:
            raise ValueError('notification default_category is unknown')
        for route in notifications['routes']:
            if route.get('category') not in category_keys:
                raise ValueError(f'notification route references unknown category {route.get("category")!r}')

        taxonomy = docs['integrations/taxonomy.yaml']
        domain_keys = unique(taxonomy['domains'], 'key', 'integration domains')
        capability_ids: set[tuple[str, str]] = set()
        for capability in taxonomy['capabilities']:
            domain_key = str(capability.get('domain_key') or '').strip()
            key = str(capability.get('key') or '').strip()
            if domain_key not in domain_keys:
                raise ValueError(f'integration capability {key!r} references unknown domain {domain_key!r}')
            identity = (domain_key, key)
            if identity in capability_ids:
                raise ValueError(f'duplicate integration capability {domain_key}.{key}')
            capability_ids.add(identity)

        compatibility = docs['integrations/compatibility.yaml']
        lifecycle_policy = compatibility.get('lifecycle_policy') or {}
        policy_year = lifecycle_policy.get('policy_year')
        lookback_years = lifecycle_policy.get('lookback_years')
        anchor_year = lifecycle_policy.get('anchor_year')
        if not all(isinstance(value, int) for value in (policy_year, lookback_years, anchor_year)):
            raise ValueError('integration compatibility lifecycle policy years must be integers')
        if anchor_year != policy_year - lookback_years:
            raise ValueError('integration compatibility anchor_year must equal policy_year - lookback_years')
        if lifecycle_policy.get('renewal_cadence') != 'annual':
            raise ValueError('integration compatibility lifecycle policy must renew annually')

        support_postures = compatibility.get('support_postures') or []
        posture_keys = unique(support_postures, 'key', 'integration compatibility support postures')
        for field in ('pre_window_posture', 'future_posture'):
            value = str(lifecycle_policy.get(field) or '').strip()
            if value not in posture_keys:
                raise ValueError(f'integration compatibility {field} references unknown posture {value!r}')

        contract_profiles = compatibility.get('contract_profiles') or []
        contract_keys = unique(contract_profiles, 'key', 'integration compatibility contract profiles')
        products = compatibility.get('products') or []
        product_keys = unique(products, 'key', 'integration compatibility products')

        contract_products: dict[str, set[str]] = {}
        for contract in contract_profiles:
            contract_key = str(contract['key'])
            declared_products = {str(value).strip() for value in contract.get('products') or () if str(value).strip()}
            if not declared_products:
                raise ValueError(f'integration compatibility contract {contract_key} must declare products')
            unknown_products = sorted(declared_products - product_keys)
            if unknown_products:
                raise ValueError(
                    f'integration compatibility contract {contract_key} references unknown products: '
                    + ', '.join(unknown_products)
                )
            contract_products[contract_key] = declared_products

        for product in products:
            product_key = str(product['key'])
            contract_key = str(product.get('contract_profile') or '').strip()
            if contract_key not in contract_keys:
                raise ValueError(
                    f'integration compatibility product {product_key} references unknown contract {contract_key!r}'
                )
            if product_key not in contract_products[contract_key]:
                raise ValueError(
                    f'integration compatibility contract {contract_key} does not declare product {product_key}'
                )
            if product.get('selection_mode') != 'automatic_detected_version':
                raise ValueError(f'integration compatibility product {product_key} must use automatic_detected_version')
            if not str(product.get('version_source') or '').strip():
                raise ValueError(f'integration compatibility product {product_key} must declare version_source')

        qualifications = compatibility.get('qualifications') or []
        qualification_keys = unique(qualifications, 'key', 'integration compatibility qualifications')
        for qualification in qualifications:
            qualification_key = str(qualification['key'])
            product_key = str(qualification.get('product') or '').strip()
            contract_key = str(qualification.get('contract_profile') or '').strip()
            support_level = str(qualification.get('support_level') or '').strip()
            if product_key not in product_keys:
                raise ValueError(
                    f'integration compatibility qualification {qualification_key} references unknown product '
                    f'{product_key!r}'
                )
            if contract_key not in contract_keys:
                raise ValueError(
                    f'integration compatibility qualification {qualification_key} references unknown contract '
                    f'{contract_key!r}'
                )
            if product_key not in contract_products[contract_key]:
                raise ValueError(
                    f'integration compatibility qualification {qualification_key} maps {product_key} '
                    f'to incompatible contract {contract_key}'
                )
            if support_level not in posture_keys:
                raise ValueError(
                    f'integration compatibility qualification {qualification_key} references unknown posture '
                    f'{support_level!r}'
                )

        qualification_by_key = {str(item['key']): item for item in qualifications}
        qualifications_by_product = {
            product_key: [item for item in qualifications if item.get('product') == product_key]
            for product_key in product_keys
        }
        contracts_by_key = {str(item['key']): item for item in contract_profiles}

        integration_provider_counts: dict[str, int] = {}
        for relative, provider_key in (
            ('integrations/orchestration/container_orchestrator/providers/kubernetes.yaml', 'kubernetes'),
            ('integrations/observability/metrics_source/contract.yaml', 'metrics_source'),
            ('integrations/observability/alert_source/providers/alertmanager.yaml', 'alertmanager'),
            ('integrations/storage/object_storage/contract.yaml', 'object_storage'),
        ):
            provider = docs[relative]
            if provider.get('provider') != provider_key:
                raise ValueError(f'{relative}: provider must be {provider_key!r}')
            provider_capabilities = provider.get('capabilities') or []
            unique(provider_capabilities, 'key', f'{provider_key} capabilities')
            integration_provider_counts[provider_key] = len(provider_capabilities)

        kubernetes = docs['integrations/orchestration/container_orchestrator/providers/kubernetes.yaml']
        expected_kubernetes_contracts = {
            str(item['contract_profile']) for item in qualifications_by_product['kubernetes']
        }
        if set(kubernetes.get('compatibility_profiles') or ()) != expected_kubernetes_contracts:
            raise ValueError('Kubernetes compatibility profiles must match central contract mappings')

        metrics_source = docs['integrations/observability/metrics_source/contract.yaml']
        expected_metrics_contracts = {
            str(item['contract_profile'])
            for product_key in ('prometheus', 'thanos')
            for item in qualifications_by_product[product_key]
        }
        if set(metrics_source.get('compatibility_profiles') or ()) != expected_metrics_contracts:
            raise ValueError('Metrics Source compatibility profiles must match central contract mappings')
        metrics_capability_keys = set(metrics_source.get('provider_capability_keys') or ())
        for contract_key in expected_metrics_contracts:
            missing = set(contracts_by_key[contract_key].get('required_capabilities') or ()) - metrics_capability_keys
            if missing:
                raise ValueError(
                    f'Metrics Source contract {contract_key} references unknown provider capabilities: '
                    f'{sorted(missing)}'
                )

        alertmanager = docs['integrations/observability/alert_source/providers/alertmanager.yaml']
        alert_capability_keys = {str(item['key']) for item in alertmanager['capabilities']}
        expected_alert_contracts = {str(item['contract_profile']) for item in qualifications_by_product['alertmanager']}
        if set(alertmanager.get('compatibility_profiles') or ()) != expected_alert_contracts:
            raise ValueError('Alertmanager compatibility profiles must match central contract mappings')
        expected_alert_qualifications = {str(item['key']) for item in qualifications_by_product['alertmanager']}
        profile_keys = unique(alertmanager['profiles'], 'key', 'Alertmanager provider qualification profiles')
        if profile_keys != expected_alert_qualifications:
            raise ValueError('Alertmanager provider qualification keys must match central qualification definitions')
        for profile in alertmanager['profiles']:
            profile_key = str(profile['key'])
            canonical = qualification_by_key[profile_key]
            if profile.get('version_constraint') != canonical.get('version_constraint'):
                raise ValueError(
                    f'Alertmanager profile {profile_key} version constraint drifted from central definition'
                )
            if profile.get('support_level') != canonical.get('support_level'):
                raise ValueError(f'Alertmanager profile {profile_key} support level drifted from central definition')
            missing = set(profile.get('required_capabilities') or ()) - alert_capability_keys
            if missing:
                raise ValueError(
                    f'Alertmanager profile {profile_key} references unknown capabilities: {sorted(missing)}'
                )
        expected_alert_core_capabilities = {
            capability
            for contract_key in expected_alert_contracts
            for capability in contracts_by_key[contract_key].get('required_capabilities') or ()
        }
        if set(alertmanager.get('core_capability_keys') or ()) != expected_alert_core_capabilities:
            raise ValueError('Alertmanager core capability keys must match the central contract requirements')

        object_storage = docs['integrations/storage/object_storage/contract.yaml']
        object_contract_key = str(object_storage.get('capability_profile') or '').strip()
        if not object_contract_key:
            raise ValueError('object-storage provider must declare capability_profile')
        object_products = object_storage.get('products') or []
        unique(object_products, 'key', 'object-storage product families')
        object_profiles = [
            profile for product in object_products for profile in product.get('compatibility_profiles') or ()
        ]
        object_profile_keys = unique(
            object_profiles,
            'key',
            'object-storage qualification profiles',
        )
        if not object_profile_keys:
            raise ValueError('object-storage provider must define at least one qualified compatibility profile')
        for profile in object_profiles:
            profile_key = str(profile['key'])
            if profile.get('contract_profile') != object_contract_key:
                raise ValueError(
                    f'object-storage profile {profile_key} must map to capability_profile {object_contract_key}'
                )
            if profile.get('support_level') not in posture_keys:
                raise ValueError(
                    f'object-storage profile {profile_key} references unknown support posture '
                    f'{profile.get("support_level")!r}'
                )

        compatibility_contract_keys = set(contract_keys) | {object_contract_key}

    except Exception as exc:
        print(f'FAIL — KAORI Definition Registry v1: {exc}', file=sys.stderr)
        return 1

    print(
        'PASS — KAORI Definition Registry v1.1 · '
        f'{len(rules)} rules · {len(permission_keys)} permissions · {len(jobs)} jobs · '
        f'{len(datasets)} analytics datasets · {len(reports["report_types"])} report types · '
        f'{len(report_coverage["domains"])} report coverage domains · '
        f'{len(domain_keys)} integration domains · {sum(integration_provider_counts.values())} provider capabilities · '
        f'{len(compatibility_contract_keys)} compatibility contracts · '
        f'{len(qualification_keys) + len(object_profile_keys)} qualification profiles'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
