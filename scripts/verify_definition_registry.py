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
    'auth/providers.yaml': 'auth_providers',
    'jobs/registered_jobs.yaml': 'registered_jobs',
    'analytics/kubernetes_datasets.yaml': 'kubernetes_analytics_datasets',
    'reports/catalog.yaml': 'report_catalog',
    'notifications/event_categories.yaml': 'notification_event_categories',
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
                raise ValueError(f"role {role['key']} references unknown permissions: {', '.join(unknown)}")

        jobs = docs['jobs/registered_jobs.yaml']['jobs']
        unique(jobs, 'key', 'registered jobs')
        unique(jobs, 'operation', 'registered jobs')
        for job in jobs:
            for field in ('configure_permission', 'execute_permission', 'domain_execute_permission'):
                value = str(job.get(field) or '').strip()
                if value and value not in permission_keys:
                    raise ValueError(f"job {job['key']} references unknown permission {value!r}")
            for field in ('dispatcher_path', 'context_builder_path'):
                value = str(job.get(field) or '')
                if ':' not in value:
                    raise ValueError(f"job {job['key']} has invalid {field}")

        runbooks = docs['knowledge/system_runbooks.yaml']['runbooks']
        unique(runbooks, 'runbook_key', 'system runbooks')
        for runbook in runbooks:
            if runbook.get('approval_policy') == 'allowed' and not runbook.get('recovery'):
                raise ValueError(f"runbook {runbook['runbook_key']} cannot auto-allow without recovery metadata")

        readiness = docs['automation/production_readiness.yaml']
        checks = readiness.get('required_checks') or []
        stages = readiness.get('rollout_stages') or []
        if len(checks) != len(set(checks)) or len(stages) != len(set(stages)):
            raise ValueError('automation readiness checks/stages must be unique')
        if not stages or stages[0] != 'disabled' or stages[-1] != 'production':
            raise ValueError('automation rollout must start disabled and end production')

        providers = docs['auth/providers.yaml']['providers']
        unique(providers, 'provider_type', 'auth providers')

        analytics = docs['analytics/kubernetes_datasets.yaml']
        datasets = list(analytics['datasets']) + [analytics['forecast_dataset']]
        unique(datasets, 'key', 'analytics datasets')
        for dataset in datasets:
            if ':' not in str(dataset.get('builder_path') or ''):
                raise ValueError(f"dataset {dataset['key']} has invalid builder_path")

        reports = docs['reports/catalog.yaml']
        formats = unique(reports['output_formats'], 'value', 'report formats')
        unique(reports['report_types'], 'value', 'report types')
        for report in reports['report_types']:
            allowed = set(report.get('allowed_formats') or ())
            if report.get('default_format') not in allowed or not allowed <= formats:
                raise ValueError(f"report {report['value']} has invalid format contract")

        notifications = docs['notifications/event_categories.yaml']
        category_keys = set(notifications['categories'])
        if notifications.get('default_category') not in category_keys:
            raise ValueError('notification default_category is unknown')
        for route in notifications['routes']:
            if route.get('category') not in category_keys:
                raise ValueError(f"notification route references unknown category {route.get('category')!r}")

    except Exception as exc:
        print(f'FAIL — KAORI Definition Registry v1: {exc}', file=sys.stderr)
        return 1

    print(
        'PASS — KAORI Definition Registry v1 · '
        f"{len(rules)} rules · {len(permission_keys)} permissions · {len(jobs)} jobs · "
        f"{len(datasets)} analytics datasets · {len(reports['report_types'])} report types"
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
