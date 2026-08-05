from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[2]
COLLECTOR_PATH = ROOT / 'app/inventory/collectors/pods.py'
SEMANTICS_PATH = ROOT / 'app/inventory/resources/pod_semantics.py'


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
            if hasattr(source, key):
                value = getattr(source, key)
                if value is not None:
                    return value
        return default

    def string_value(value, default: str = '-') -> str:
        return default if value in (None, '') else str(value)

    common_module._model_value = model_value
    common_module._string_value = string_value
    common_module._isoformat_datetime = lambda value: (
        value.isoformat()
        if hasattr(value, 'isoformat')
        else (None if value in (None, '') else str(value))
    )
    common_module._toleration_display = lambda value: str(value)

    kubernetes_module = ModuleType('kubernetes')
    client_module = ModuleType('kubernetes.client')
    exceptions_module = ModuleType('kubernetes.client.exceptions')

    for name in (
        'AppsV1Api',
        'BatchV1Api',
        'CoreV1Api',
        'V1JobList',
        'V1PodList',
        'V1ReplicaSetList',
    ):
        setattr(client_module, name, type(name, (), {}))

    class ApiException(Exception):
        def __init__(self, status=None):
            super().__init__(status)
            self.status = status

    exceptions_module.ApiException = ApiException

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

    spec = importlib.util.spec_from_file_location('pod_collector_under_test', COLLECTOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, ApiException


def _load_semantics():
    spec = importlib.util.spec_from_file_location('pod_semantics_under_test', SEMANTICS_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metadata(
    name: str | None = 'api-7d9f',
    *,
    namespace: str | None = 'payments',
    deletion_timestamp=None,
    owner_references=None,
):
    return SimpleNamespace(
        namespace=namespace,
        name=name,
        uid=f'uid-{name}',
        labels={'app': 'api'},
        annotations={},
        deletion_timestamp=deletion_timestamp,
        owner_references=owner_references or [],
        creation_timestamp=datetime(2026, 8, 5, tzinfo=UTC),
    )


def _container(name: str, image: str, *, env_from=None, volume_mounts=None):
    return SimpleNamespace(
        name=name,
        image=image,
        image_pull_policy='IfNotPresent',
        env_from=env_from or [],
        env=[],
        volume_mounts=volume_mounts or [],
    )


def _spec(*, regular=None, init=None, ephemeral=None, volumes=None):
    return SimpleNamespace(
        containers=regular or [_container('api', 'registry/api:1')],
        init_containers=init or [],
        ephemeral_containers=ephemeral or [],
        volumes=volumes or [],
        image_pull_secrets=[],
        node_name='worker-1',
        scheduler_name='default-scheduler',
        priority_class_name=None,
        node_selector={},
        tolerations=[],
        affinity=None,
        topology_spread_constraints=[],
        host_network=False,
        service_account_name='default',
        restart_policy='Always',
        dns_policy='ClusterFirst',
        runtime_class_name=None,
        security_context=None,
    )


def _pod(*, metadata=None, spec=None, status=None):
    return SimpleNamespace(
        metadata=metadata or _metadata(),
        spec=spec or _spec(),
        status=status,
    )


def _core_api(pods):
    return SimpleNamespace(list_pod_for_all_namespaces=lambda: SimpleNamespace(items=pods))


def _empty_apps_api():
    return SimpleNamespace(list_replica_set_for_all_namespaces=lambda: SimpleNamespace(items=[]))


def _empty_batch_api():
    return SimpleNamespace(list_job_for_all_namespaces=lambda: SimpleNamespace(items=[]))


def test_missing_container_statuses_are_not_manufactured_as_zero_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, _ = _load_collector(monkeypatch)
    pod = _pod(
        spec=_spec(
            regular=[
                _container('api', 'registry/api:1'),
                _container('sidecar', 'registry/sidecar:1'),
            ]
        ),
        status=SimpleNamespace(
            phase='Running',
            container_statuses=None,
            init_container_statuses=None,
            ephemeral_container_statuses=None,
            conditions=None,
            pod_ip='10.0.0.10',
            host_ip='10.0.0.1',
            reason=None,
            message=None,
            qos_class='Burstable',
        ),
    )

    row = collector.get_pods(_core_api([pod]), _empty_apps_api(), _empty_batch_api())[0]
    semantics = _load_semantics()

    assert row['ready'] == 'Not Reported'
    assert row['restart_count'] == 0
    assert row['details']['runtime_evidence_reported'] is False
    assert row['details']['configuration']['container_count'] == 2
    assert semantics.pod_operational_state(row['phase'], row['ready'])[0] == 'Unknown'


def test_deletion_timestamp_creates_terminating_lifecycle_without_losing_raw_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, _ = _load_collector(monkeypatch)
    deletion_timestamp = datetime(2026, 8, 5, 5, 30, tzinfo=UTC)
    pod = _pod(
        metadata=_metadata(deletion_timestamp=deletion_timestamp),
        status=SimpleNamespace(
            phase='Running',
            container_statuses=[],
            init_container_statuses=[],
            ephemeral_container_statuses=[],
            conditions=[],
            pod_ip=None,
            host_ip=None,
            reason=None,
            message=None,
            qos_class='Burstable',
        ),
    )

    row = collector.get_pods(_core_api([pod]), _empty_apps_api(), _empty_batch_api())[0]

    assert row['phase'] == 'Terminating'
    assert row['details']['kubernetes_phase'] == 'Running'
    assert row['details']['deletion_timestamp'] == deletion_timestamp.isoformat()


def test_ephemeral_containers_contribute_runtime_image_mount_and_reference_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, _ = _load_collector(monkeypatch)
    config_map_ref = SimpleNamespace(config_map_ref=SimpleNamespace(name='debug-config'), secret_ref=None)
    ephemeral = _container(
        'debugger',
        'registry/debug:1',
        env_from=[config_map_ref],
        volume_mounts=[SimpleNamespace(name='shared')],
    )
    init = _container('migrate', 'registry/migrate:1')
    volume = SimpleNamespace(
        name='shared',
        config_map=SimpleNamespace(name='shared-config'),
        secret=None,
        persistent_volume_claim=None,
        csi=None,
        host_path=None,
        empty_dir=None,
        projected=None,
        downward_api=None,
        ephemeral=None,
    )
    regular_status = SimpleNamespace(
        name='api',
        ready=True,
        started=True,
        restart_count=1,
        state=None,
        last_state=None,
        image='registry/api:1',
        image_id='sha256:a',
    )
    init_status = SimpleNamespace(
        name='migrate',
        ready=True,
        started=True,
        restart_count=2,
        state=None,
        last_state=None,
        image='registry/migrate:1',
        image_id='sha256:b',
    )
    ephemeral_status = SimpleNamespace(
        name='debugger',
        ready=True,
        started=True,
        restart_count=3,
        state=None,
        last_state=None,
        image='registry/debug:1',
        image_id='sha256:c',
    )
    pod = _pod(
        spec=_spec(init=[init], ephemeral=[ephemeral], volumes=[volume]),
        status=SimpleNamespace(
            phase='Running',
            container_statuses=[regular_status],
            init_container_statuses=[init_status],
            ephemeral_container_statuses=[ephemeral_status],
            conditions=[],
            pod_ip='10.0.0.10',
            host_ip='10.0.0.1',
            reason=None,
            message=None,
            qos_class='Burstable',
        ),
    )

    row = collector.get_pods(_core_api([pod]), _empty_apps_api(), _empty_batch_api())[0]

    assert row['restart_count'] == 6
    assert row['image_count'] == 3
    assert 'registry/debug:1' in row['init_container_images']
    assert {'type': 'ConfigMap', 'name': 'debug-config'} in row['configuration_references']
    assert row['details']['volumes'][0]['mounted_by'] == ['debugger']
    kinds = {item['kind'] for item in row['details']['container_statuses']}
    assert kinds == {'Regular', 'Init', 'Ephemeral'}


def test_owner_enrichment_permission_failure_does_not_abort_pod_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector, ApiException = _load_collector(monkeypatch)
    owner = SimpleNamespace(kind='ReplicaSet', name='api-7d9f', controller=True)
    pod = _pod(
        metadata=_metadata(owner_references=[owner]),
        status=SimpleNamespace(
            phase='Pending',
            container_statuses=[],
            init_container_statuses=[],
            ephemeral_container_statuses=[],
            conditions=[],
            pod_ip=None,
            host_ip=None,
            reason=None,
            message=None,
            qos_class=None,
        ),
    )

    def denied():
        raise ApiException(403)

    rows, evidence = collector.get_pods(
        _core_api([pod]),
        SimpleNamespace(list_replica_set_for_all_namespaces=denied),
        _empty_batch_api(),
        with_evidence=True,
    )

    assert len(rows) == 1
    assert rows[0]['workload_type'] == 'ReplicaSet'
    assert rows[0]['workload_name'] == 'api-7d9f'
    assert rows[0]['details']['owner_resolution']['replica_set_lookup'] == 'Permission Unavailable'
    assert evidence['inventory.pods.owner-resolution.replicasets'] == 'Permission Unavailable'


def test_pods_without_namespace_or_name_are_not_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    collector, _ = _load_collector(monkeypatch)
    invalid = [
        _pod(metadata=_metadata(namespace=None)),
        _pod(metadata=_metadata(name=None)),
    ]

    rows = collector.get_pods(_core_api(invalid), _empty_apps_api(), _empty_batch_api())

    assert rows == []


def test_condition_and_container_presentations_preserve_kubernetes_semantics() -> None:
    semantics = _load_semantics()

    sandbox = semantics.condition_presentation(
        {'type': 'PodReadyToStartContainers', 'status': 'False', 'reason': 'PodSandboxChanged'}
    )
    disruption = semantics.condition_presentation(
        {'type': 'DisruptionTarget', 'status': 'Unknown'}
    )
    image_pull = semantics.container_presentation(
        {
            'name': 'api',
            'kind': 'Regular',
            'state': 'Waiting',
            'reason': 'ImagePullBackOff',
            'ready': False,
            'restart_count': 0,
            'exit_code': None,
        }
    )
    unknown_exit = semantics.container_presentation(
        {
            'name': 'api',
            'kind': 'Regular',
            'state': 'Terminated',
            'reason': None,
            'ready': False,
            'restart_count': 0,
            'exit_code': None,
        }
    )

    assert sandbox['state_label'] == 'Runtime Sandbox Pending'
    assert sandbox['state_tone'] == 'pending'
    assert disruption['state_label'] == 'Unknown'
    assert disruption['state_tone'] == 'unknown'
    assert image_pull['runtime_state_label'] == 'ImagePullBackOff'
    assert image_pull['runtime_state_tone'] == 'critical'
    assert unknown_exit['runtime_state_label'] == 'Unknown'
    assert unknown_exit['runtime_state_tone'] == 'unknown'
