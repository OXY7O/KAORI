from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def _load(monkeypatch, name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def _load_workload_modules(monkeypatch):
    for name in ('app', 'app.analytics', 'app.analytics.common', 'app.analytics.workload'):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))

    base_service = ModuleType('app.analytics.common.base_service')
    base_service.bytes_to_gib = lambda value: round(value / 1024**3, 2)
    base_service.safe_round = round
    base_service.safe_percent = lambda value, total: max(0, min(value / total * 100, 100)) if total else 0
    base_service.raw_percent = lambda value, total: value / total * 100 if total else 0
    monkeypatch.setitem(sys.modules, 'app.analytics.common.base_service', base_service)

    coercion = ModuleType('app.analytics.common.coercion')
    coercion.safe_float = lambda value: float(value or 0)
    monkeypatch.setitem(sys.modules, 'app.analytics.common.coercion', coercion)

    _load(monkeypatch, 'app.analytics.workload.formatting', 'app/analytics/workload/formatting.py')
    quota = _load(monkeypatch, 'app.analytics.workload.quota', 'app/analytics/workload/quota.py')
    mapping = _load(monkeypatch, 'app.analytics.workload.mapping', 'app/analytics/workload/mapping.py')
    domain = _load(monkeypatch, 'app.analytics.workload.domain', 'app/analytics/workload/domain.py')
    return quota, mapping, domain


def test_multiple_resource_quota_objects_remain_independent(monkeypatch) -> None:
    quota, _, _ = _load_workload_modules(monkeypatch)
    summary = quota.build_tenant_quota_summary(
        active_namespaces={'payments': 1},
        hard={
            'payments': {
                'team-small': {
                    'requests.cpu': 1,
                    'limits.cpu': 2,
                    'requests.memory': 2 * 1024**3,
                    'limits.memory': 4 * 1024**3,
                    'pods': 10,
                },
                'team-large': {
                    'requests.cpu': 4,
                    'limits.cpu': 8,
                    'requests.memory': 8 * 1024**3,
                    'limits.memory': 16 * 1024**3,
                    'pods': 40,
                },
            }
        },
        used={
            'payments': {
                'team-small': {
                    'requests.cpu': 0.9,
                    'limits.cpu': 1.8,
                    'requests.memory': 1 * 1024**3,
                    'limits.memory': 2 * 1024**3,
                    'pods': 8,
                },
                'team-large': {
                    'requests.cpu': 1,
                    'limits.cpu': 2,
                    'requests.memory': 2 * 1024**3,
                    'limits.memory': 4 * 1024**3,
                    'pods': 8,
                },
            }
        },
        cpu_actual={'payments': 1.5},
        memory_actual={'payments': 3 * 1024**3},
        pod_actual={'payments': 7},
    )

    row = summary['rows'][0]
    assert row['quota_object_count'] == 2
    assert row['quota_pressure_object'] == 'team-small'
    assert row['quota_usage_percent'] == 90.0
    assert row['runtime_demand_object'] == 'team-small'
    assert row['runtime_demand_available'] is True


def test_zero_quota_key_is_configured_but_not_pressure_evidence(monkeypatch) -> None:
    quota, _, _ = _load_workload_modules(monkeypatch)
    summary = quota.build_tenant_quota_summary(
        active_namespaces={'sandbox': 1},
        hard={
            'sandbox': {
                'default': {
                    'requests.cpu': 0,
                    'limits.cpu': 0,
                    'requests.memory': 0,
                    'limits.memory': 0,
                    'pods': 0,
                }
            }
        },
        used={'sandbox': {'default': {}}},
        cpu_actual={},
        memory_actual={},
        pod_actual={},
    )

    row = summary['rows'][0]
    assert row['quota_status']['label'] == 'Complete'
    assert row['missing_keys'] == []
    assert row['quota_pressure_available'] is False
    assert row['risk']['label'] == 'Unknown'


def test_owner_kind_is_part_of_workload_identity(monkeypatch) -> None:
    _, mapping, _ = _load_workload_modules(monkeypatch)
    evidence = mapping.WorkloadMappingEvidence(
        cpu_requests={'apps/pod-a': 1, 'apps/pod-b': 1},
        cpu_limits={},
        cpu_current={'apps/pod-a': 0.5, 'apps/pod-b': 0.5},
        cpu_peak={'apps/pod-a': 0.7, 'apps/pod-b': 0.7},
        memory_requests={'apps/pod-a': 1024, 'apps/pod-b': 1024},
        memory_limits={},
        memory_current={'apps/pod-a': 512, 'apps/pod-b': 512},
        memory_peak={'apps/pod-a': 700, 'apps/pod-b': 700},
        owner_map={
            'apps/pod-a': {'kind': 'Deployment', 'name': 'api'},
            'apps/pod-b': {'kind': 'StatefulSet', 'name': 'api'},
        },
        qos_map={'apps/pod-a': 'Burstable', 'apps/pod-b': 'Burstable'},
    )
    payload = mapping.build_workload_mapping_payload(evidence)

    assert [(row['type'], row['workload']) for row in payload['rows']] == [
        ('Deployment', 'api'),
        ('StatefulSet', 'api'),
    ]


def test_posture_never_claims_healthy_without_complete_evidence(monkeypatch) -> None:
    _, _, domain = _load_workload_modules(monkeypatch)

    assert domain.build_workload_posture([], [], [])['value'] == 'Unknown'
    limited = domain.build_workload_posture(
        [
            {
                'quota_status': {'label': 'Complete'},
                'quota_pressure_available': False,
                'runtime_demand_available': False,
            }
        ],
        [
            {
                'request_coverage': {'label': 'Complete'},
                'metrics_coverage': {'label': 'Partial'},
                'risk': {'label': 'Unknown'},
            }
        ],
        [],
    )
    assert limited['value'] == 'Limited Evidence'


def test_zero_request_or_limit_series_remains_unconfigured(monkeypatch) -> None:
    _, mapping, _ = _load_workload_modules(monkeypatch)
    evidence = mapping.WorkloadMappingEvidence(
        cpu_requests={'apps/pod-a': 0},
        cpu_limits={'apps/pod-a': 0},
        cpu_current={'apps/pod-a': 0},
        cpu_peak={'apps/pod-a': 0},
        memory_requests={'apps/pod-a': 0},
        memory_limits={'apps/pod-a': 0},
        memory_current={'apps/pod-a': 0},
        memory_peak={'apps/pod-a': 0},
        owner_map={'apps/pod-a': {'kind': 'Deployment', 'name': 'api'}},
        qos_map={'apps/pod-a': 'BestEffort'},
    )

    row = mapping.build_workload_mapping_payload(evidence)['rows'][0]
    assert row['request_coverage']['label'] == 'Missing'
    assert row['limit_coverage']['label'] == 'Limits Unset'
    assert row['cpu_request'] == 'Unset'
    assert row['memory_request'] == 'Unset'
    assert row['metrics_coverage']['label'] == 'Complete'
    assert row['cpu_request_utilization_available'] is False
