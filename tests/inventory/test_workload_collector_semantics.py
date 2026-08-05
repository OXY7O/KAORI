from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[2]
COLLECTOR_PATH = ROOT / 'app/inventory/collectors/workloads.py'


def _load_collector(monkeypatch: pytest.MonkeyPatch):
    app_module = ModuleType('app')
    inventory_module = ModuleType('app.inventory')
    collectors_module = ModuleType('app.inventory.collectors')
    common_module = ModuleType('app.inventory.collectors.common')

    def model_value(source, *keys: str, default=None):
        if source is None:
            return default
        for key in keys:
            if isinstance(source, dict) and key in source:
                return source[key]
            value = getattr(source, key, None)
            if value is not None:
                return value
        return default

    def string_value(value, default: str = '-') -> str:
        return default if value in (None, '') else str(value)

    def detail_row(label, value):
        return {'label': str(label), 'value': '-' if value in (None, '') else str(value)}

    def isoformat_datetime(value):
        return value.isoformat() if hasattr(value, 'isoformat') else ('-' if value in (None, '') else str(value))

    def metadata_details(metadata):
        return {
            'uid': getattr(metadata, 'uid', None),
            'labels': getattr(metadata, 'labels', None) or {},
            'annotations': getattr(metadata, 'annotations', None) or {},
        }

    common_module._model_value = model_value
    common_module._string_value = string_value
    common_module._detail_row = detail_row
    common_module._isoformat_datetime = isoformat_datetime
    common_module._metadata_details = metadata_details
    common_module._to_modelish = lambda value: value
    common_module._toleration_display = lambda value: str(value)

    kubernetes_module = ModuleType('kubernetes')
    client_module = ModuleType('kubernetes.client')
    exceptions_module = ModuleType('kubernetes.client.exceptions')

    for name in (
        'AppsV1Api',
        'BatchV1Api',
        'V1CronJobList',
        'V1DaemonSetList',
        'V1DeploymentList',
        'V1JobList',
        'V1StatefulSetList',
    ):
        setattr(client_module, name, type(name, (), {}))

    class ApiException(Exception):
        def __init__(self, status=None):
            super().__init__(status)
            self.status = status

    class NotFoundException(ApiException):
        pass

    exceptions_module.ApiException = ApiException
    exceptions_module.NotFoundException = NotFoundException

    modules = {
        'app': app_module,
        'app.inventory': inventory_module,
        'app.inventory.collectors': collectors_module,
        'app.inventory.collectors.common': common_module,
        'kubernetes': kubernetes_module,
        'kubernetes.client': client_module,
        'kubernetes.client.exceptions': exceptions_module,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = importlib.util.spec_from_file_location('workload_collector_under_test', COLLECTOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metadata(name: str = 'api', *, generation: int = 1):
    return SimpleNamespace(
        namespace='payments',
        name=name,
        uid=f'uid-{name}',
        labels={},
        annotations={},
        generation=generation,
        creation_timestamp=datetime(2026, 8, 5, tzinfo=UTC),
    )


def _pod_template():
    container = SimpleNamespace(name='api', image='registry/api:1', image_pull_policy='IfNotPresent')
    pod_spec = SimpleNamespace(
        containers=[container],
        init_containers=[],
        service_account_name='default',
        restart_policy='Always',
        priority_class_name=None,
        scheduler_name='default-scheduler',
        host_network=False,
        dns_policy='ClusterFirst',
        volumes=[],
        node_selector={},
        affinity=None,
        tolerations=[],
        topology_spread_constraints=[],
        runtime_class_name=None,
    )
    return SimpleNamespace(spec=pod_spec)


def _apps_api(*, deployments=None, statefulsets=None, daemonsets=None):
    return SimpleNamespace(
        list_deployment_for_all_namespaces=lambda: SimpleNamespace(items=deployments or []),
        list_stateful_set_for_all_namespaces=lambda: SimpleNamespace(items=statefulsets or []),
        list_daemon_set_for_all_namespaces=lambda: SimpleNamespace(items=daemonsets or []),
    )


def _batch_api(*, jobs=None, cronjobs=None):
    return SimpleNamespace(
        list_job_for_all_namespaces=lambda: SimpleNamespace(items=jobs or []),
        list_cron_job_for_all_namespaces=lambda: SimpleNamespace(items=cronjobs or []),
    )


def test_missing_deployment_status_is_unknown_not_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    collector = _load_collector(monkeypatch)
    deployment = SimpleNamespace(
        metadata=_metadata(),
        spec=SimpleNamespace(
            replicas=1,
            strategy=SimpleNamespace(type='RollingUpdate', rolling_update=None),
            template=_pod_template(),
            min_ready_seconds=0,
            progress_deadline_seconds=600,
            revision_history_limit=10,
        ),
        status=None,
    )

    rows = collector.get_workloads(_apps_api(deployments=[deployment]))

    assert rows[0]['status'] == 'Unknown'
    assert rows[0]['details']['state_display'] == 'Runtime State Not Reported'
    assert rows[0]['details']['status_reported'] is False


def test_deployment_progress_deadline_is_failed_and_export_fields_are_flattened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector = _load_collector(monkeypatch)
    condition = SimpleNamespace(
        type='Progressing',
        status='False',
        reason='ProgressDeadlineExceeded',
        message='ReplicaSet did not progress.',
        last_transition_time=datetime(2026, 8, 5, tzinfo=UTC),
    )
    deployment = SimpleNamespace(
        metadata=_metadata(generation=3),
        spec=SimpleNamespace(
            replicas=3,
            strategy=SimpleNamespace(
                type='RollingUpdate',
                rolling_update=SimpleNamespace(max_surge='25%', max_unavailable='25%'),
            ),
            template=_pod_template(),
            min_ready_seconds=0,
            progress_deadline_seconds=600,
            revision_history_limit=10,
        ),
        status=SimpleNamespace(
            replicas=3,
            updated_replicas=2,
            ready_replicas=2,
            available_replicas=2,
            unavailable_replicas=1,
            observed_generation=3,
            conditions=[condition],
        ),
    )

    row = collector.get_workloads(_apps_api(deployments=[deployment]))[0]

    assert row['status'] == 'Failed'
    assert row['details']['desired_replicas'] == 3
    assert row['details']['updated_replicas'] == 2
    assert row['details']['available_replicas'] == 2
    assert row['details']['unavailable_replicas'] == 1
    assert row['details']['update_strategy'] == 'RollingUpdate'
    assert row['details']['conditions'][0]['reason'] == 'ProgressDeadlineExceeded'


def test_job_failed_pod_attempt_does_not_mean_job_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    collector = _load_collector(monkeypatch)
    job = SimpleNamespace(
        metadata=_metadata('reconcile'),
        spec=SimpleNamespace(
            completions=1,
            parallelism=1,
            suspend=False,
            backoff_limit=6,
            completion_mode='NonIndexed',
            active_deadline_seconds=None,
            ttl_seconds_after_finished=None,
            template=_pod_template(),
        ),
        status=SimpleNamespace(active=1, succeeded=0, failed=1, conditions=[]),
    )

    row = collector.get_workloads(_apps_api(), _batch_api(jobs=[job]))[0]

    assert row['status'] == 'Progressing'
    assert row['details']['state_display'] == '1 Active'


def test_completed_and_suspended_jobs_use_canonical_posture(monkeypatch: pytest.MonkeyPatch) -> None:
    collector = _load_collector(monkeypatch)
    complete_condition = SimpleNamespace(
        type='Complete',
        status='True',
        reason='CompletionsReached',
        message='Job completed.',
        last_transition_time=None,
    )
    completed = SimpleNamespace(
        metadata=_metadata('completed'),
        spec=SimpleNamespace(
            completions=1,
            parallelism=1,
            suspend=False,
            backoff_limit=6,
            completion_mode='NonIndexed',
            active_deadline_seconds=None,
            ttl_seconds_after_finished=None,
            template=_pod_template(),
        ),
        status=SimpleNamespace(active=0, succeeded=1, failed=0, conditions=[complete_condition]),
    )
    suspended = SimpleNamespace(
        metadata=_metadata('paused'),
        spec=SimpleNamespace(
            completions=1,
            parallelism=1,
            suspend=True,
            backoff_limit=6,
            completion_mode='NonIndexed',
            active_deadline_seconds=None,
            ttl_seconds_after_finished=None,
            template=_pod_template(),
        ),
        status=None,
    )

    rows = collector.get_workloads(_apps_api(), _batch_api(jobs=[completed, suspended]))

    assert [row['status'] for row in rows] == ['Stable', 'Suspended']


def test_deployment_requires_current_generation_before_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    collector = _load_collector(monkeypatch)
    deployment = SimpleNamespace(
        metadata=_metadata(generation=5),
        spec=SimpleNamespace(
            replicas=2,
            strategy=SimpleNamespace(type='RollingUpdate', rolling_update=None),
            template=_pod_template(),
            min_ready_seconds=0,
            progress_deadline_seconds=600,
            revision_history_limit=10,
        ),
        status=SimpleNamespace(
            replicas=2,
            updated_replicas=2,
            ready_replicas=2,
            available_replicas=2,
            unavailable_replicas=0,
            observed_generation=4,
            conditions=[],
        ),
    )

    row = collector.get_workloads(_apps_api(deployments=[deployment]))[0]

    assert row['status'] == 'Progressing'
    assert row['details']['generation'] == 5
    assert row['details']['observed_generation'] == 4


def test_deployment_replica_failure_is_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    collector = _load_collector(monkeypatch)
    condition = SimpleNamespace(
        type='ReplicaFailure',
        status='True',
        reason='FailedCreate',
        message='Admission policy rejected the Pod.',
        last_transition_time=None,
    )
    deployment = SimpleNamespace(
        metadata=_metadata(generation=2),
        spec=SimpleNamespace(
            replicas=1,
            strategy=SimpleNamespace(type='RollingUpdate', rolling_update=None),
            template=_pod_template(),
            min_ready_seconds=0,
            progress_deadline_seconds=600,
            revision_history_limit=10,
        ),
        status=SimpleNamespace(
            replicas=0,
            updated_replicas=0,
            ready_replicas=0,
            available_replicas=0,
            unavailable_replicas=1,
            observed_generation=2,
            conditions=[condition],
        ),
    )

    row = collector.get_workloads(_apps_api(deployments=[deployment]))[0]

    assert row['status'] == 'Failed'
    assert row['details']['state_display'] == 'Replica Failure Reported'
