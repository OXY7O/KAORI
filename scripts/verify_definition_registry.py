#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = ROOT / 'app' / 'definitions' / 'catalogs'

EXPECTED = {
    'intelligence/rules.yaml': 'intelligence_rules',
    'rbac/access.yaml': 'rbac_access',
    'knowledge/system_runbooks.yaml': 'system_runbooks',
    'automation/production_readiness.yaml': 'automation_production_readiness',
    'auth/identity_provider/providers.yaml': 'identity_providers',
    'jobs/registered_jobs.yaml': 'registered_jobs',
    'analytics/kubernetes_datasets.yaml': 'kubernetes_analytics_datasets',
    'reports/catalog.yaml': 'report_catalog',
    'reports/coverage.yaml': 'report_coverage_catalog',
    'notifications/event_categories.yaml': 'notification_event_categories',
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
    data = yaml.load(path.read_text(encoding='utf-8'), Loader=StrictLoader)
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

        access = docs['rbac/access.yaml']
        permission_keys = unique(access['permissions'], 'key', 'permissions')
        unique(access['system_roles'], 'key', 'system roles')
        for role in access['system_roles']:
            unknown = sorted(set(role.get('permissions') or ()) - permission_keys)
            if unknown:
                raise ValueError(f'role {role["key"]} references unknown permissions: {", ".join(unknown)}')

        jobs = docs['jobs/registered_jobs.yaml']['jobs']
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

        runbooks = docs['knowledge/system_runbooks.yaml']['runbooks']
        unique(runbooks, 'runbook_key', 'system runbooks')
        for runbook in runbooks:
            if runbook.get('approval_policy') == 'allowed' and not runbook.get('recovery'):
                raise ValueError(f'runbook {runbook["runbook_key"]} cannot auto-allow without recovery metadata')

        readiness = docs['automation/production_readiness.yaml']
        checks = readiness.get('required_checks') or []
        stages = readiness.get('rollout_stages') or []
        if len(checks) != len(set(checks)) or len(stages) != len(set(stages)):
            raise ValueError('automation readiness checks/stages must be unique')
        if not stages or stages[0] != 'disabled' or stages[-1] != 'production':
            raise ValueError('automation rollout must start disabled and end production')

        providers = docs['auth/identity_provider/providers.yaml']['providers']
        unique(providers, 'provider_key', 'identity providers')

        analytics = docs['analytics/kubernetes_datasets.yaml']
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

        notifications = docs['notifications/event_categories.yaml']
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
        compatibility_profiles = unique(compatibility['profiles'], 'key', 'integration compatibility profiles')
        if not compatibility.get('kubernetes_lifecycle_policy'):
            raise ValueError('integration compatibility Kubernetes lifecycle policy is missing')

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

        alertmanager = docs['integrations/observability/alert_source/providers/alertmanager.yaml']
        alert_capability_keys = {str(item['key']) for item in alertmanager['capabilities']}
        profile_keys = unique(alertmanager['profiles'], 'key', 'Alertmanager provider profiles')
        for profile in alertmanager['profiles']:
            missing = set(profile.get('required_capabilities') or ()) - alert_capability_keys
            if missing:
                raise ValueError(
                    f'Alertmanager profile {profile["key"]} references unknown capabilities: {sorted(missing)}'
                )
        if set(alertmanager.get('compatibility_profiles') or ()) != profile_keys:
            raise ValueError('Alertmanager compatibility profile keys must match provider profile definitions')

        object_storage = docs['integrations/storage/object_storage/contract.yaml']
        products = object_storage.get('products') or []
        unique(products, 'key', 'object-storage product families')
        object_profile_keys = {
            str(profile['key']) for product in products for profile in product.get('compatibility_profiles') or ()
        }
        if not object_profile_keys:
            raise ValueError('object-storage provider must define at least one qualified compatibility profile')

    except Exception as exc:
        print(f'FAIL — KAORI Definition Registry v1: {exc}', file=sys.stderr)
        return 1

    print(
        'PASS — KAORI Definition Registry v1.1 · '
        f'{len(rules)} rules · {len(permission_keys)} permissions · {len(jobs)} jobs · '
        f'{len(datasets)} analytics datasets · {len(reports["report_types"])} report types · '
        f'{len(report_coverage["domains"])} report coverage domains · '
        f'{len(domain_keys)} integration domains · {sum(integration_provider_counts.values())} provider capabilities · '
        f'{len(compatibility_profiles)} compatibility profiles'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
