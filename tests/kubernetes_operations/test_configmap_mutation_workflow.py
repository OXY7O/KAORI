from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[2]
SERVICE_PATH = ROOT / 'app/kubernetes_operations/configmaps/service.py'
CONTRACTS_PATH = ROOT / 'app/kubernetes_operations/configmaps/contracts.py'


def _simple_type(name: str):
    class Value:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    Value.__name__ = name
    return Value


def load_service(monkeypatch: pytest.MonkeyPatch):
    modules: dict[str, ModuleType] = {}
    for name in (
        'app',
        'app.common',
        'app.common.inventory_generation',
        'app.inventory',
        'app.inventory.resources.configuration_semantics',
        'app.inventory.resources',
        'app.inventory.resources.pod_semantics',
        'app.kubernetes_operations',
        'app.kubernetes_operations.configmaps',
        'app.kubernetes_operations.configmaps.runtime',
        'app.kubernetes_operations.configmaps.validation',
        'app.models',
        'kubernetes',
        'kubernetes.client',
        'kubernetes.client.exceptions',
    ):
        modules[name] = ModuleType(name)
        monkeypatch.setitem(sys.modules, name, modules[name])

    evidence = modules['app.inventory.resources.configuration_semantics']
    evidence.COLLECTED = 'Collected'
    evidence.POD_EVIDENCE_KEY = 'inventory.pods'
    evidence.collection_state = lambda payload, key: payload.get(key, 'Not Reported')
    modules['app.common.inventory_generation'].filter_current_generation = lambda query, model: query
    modules['app.inventory.resources.pod_semantics'].pod_operational_state = (
        lambda phase, ready: ('Ready', 'normal', 'Running · 1/1 Ready')
    )

    contracts_spec = importlib.util.spec_from_file_location(
        'app.kubernetes_operations.configmaps.contracts',
        CONTRACTS_PATH,
    )
    assert contracts_spec and contracts_spec.loader
    contracts = importlib.util.module_from_spec(contracts_spec)
    monkeypatch.setitem(
        sys.modules,
        'app.kubernetes_operations.configmaps.contracts',
        contracts,
    )
    contracts_spec.loader.exec_module(contracts)

    runtime = modules['app.kubernetes_operations.configmaps.runtime']
    runtime.authorization_call = lambda cluster, operation, callback: callback(None)
    runtime.live_call = lambda cluster, operation, callback: callback(None)
    runtime.safe_api_error = lambda exc, operation: ValueError(f'{operation} failed')

    validation = modules['app.kubernetes_operations.configmaps.validation']
    validation.diff_entries = lambda existing, proposed: {}
    validation.merge_entries = lambda existing, submitted, mode: submitted
    validation.normalize_update_mode = lambda value: value or 'merge'
    validation.parse_entries = lambda form: None
    validation.validate_name = lambda value, label: value
    validation.validate_namespace_name = lambda value: value

    models = modules['app.models']
    for name in ('Cluster', 'ClusterInventory', 'ConfigurationInventory', 'PodInventory'):
        setattr(models, name, type(name, (), {}))

    client = modules['kubernetes.client']
    for name in (
        'V1ConfigMap',
        'V1ObjectMeta',
        'V1ConfigMapList',
        'V1NamespaceList',
        'V1SelfSubjectAccessReview',
        'V1SelfSubjectAccessReviewSpec',
        'V1ResourceAttributes',
        'V1DeleteOptions',
        'V1Preconditions',
    ):
        setattr(client, name, _simple_type(name))
    modules['kubernetes'].client = client

    class ApiException(Exception):
        def __init__(self, status=None):
            super().__init__(status)
            self.status = status

    modules['kubernetes.client.exceptions'].ApiException = ApiException

    spec = importlib.util.spec_from_file_location('configmap_service_under_test', SERVICE_PATH)
    assert spec and spec.loader
    service = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(service)
    return service


def target():
    return SimpleNamespace(
        cluster=SimpleNamespace(id=7, name='Development'),
        namespace='default',
        name='application-config',
    )


def form() -> dict[str, str]:
    return {'confirm_name': 'application-config'}


def live_payload(resource_version: str = '101') -> dict[str, object]:
    return {
        'resource_version': resource_version,
        'data': {'key': 'value'},
        'binary_data': {},
    }


def impact():
    return SimpleNamespace(count=0, collection_state='Collected')


def test_delete_validation_uses_non_destructive_authorization_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    service = load_service(monkeypatch)
    reviews: list[object] = []

    monkeypatch.setattr(service, '_bound_target', lambda submitted: target())
    monkeypatch.setattr(service, 'read_configmap', lambda selected: live_payload())
    monkeypatch.setattr(service, 'get_impact_context', lambda selected: impact())
    monkeypatch.setattr(
        service,
        'live_call',
        lambda *args, **kwargs: pytest.fail('Validation must not call the ConfigMap DELETE endpoint.'),
    )

    authorization_api = SimpleNamespace(
        create_self_subject_access_review=lambda **kwargs: (
            reviews.append(kwargs['body'])
            or SimpleNamespace(status=SimpleNamespace(allowed=True))
        )
    )
    monkeypatch.setattr(
        service,
        'authorization_call',
        lambda cluster, operation, callback: callback(authorization_api),
    )

    result = service.delete_configmap(form(), validate_only=True)

    assert len(reviews) == 1
    attributes = reviews[0].spec.resource_attributes
    assert attributes.resource == 'configmaps'
    assert attributes.verb == 'delete'
    assert attributes.namespace == 'default'
    assert attributes.name == 'application-config'
    assert result['operation'] == 'validation'
    assert result['validation_mode'] == 'authorization_preflight'
    assert result['resource_version'] == '101'


def test_delete_validation_rejects_missing_delete_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    service = load_service(monkeypatch)
    monkeypatch.setattr(service, '_bound_target', lambda submitted: target())
    monkeypatch.setattr(service, 'read_configmap', lambda selected: live_payload())
    monkeypatch.setattr(service, 'get_impact_context', lambda selected: impact())

    authorization_api = SimpleNamespace(
        create_self_subject_access_review=lambda **kwargs: SimpleNamespace(
            status=SimpleNamespace(allowed=False)
        )
    )
    monkeypatch.setattr(
        service,
        'authorization_call',
        lambda cluster, operation, callback: callback(authorization_api),
    )

    with pytest.raises(ValueError, match='denied ConfigMap deletion'):
        service.delete_configmap(form(), validate_only=True)


def test_final_delete_executes_once_without_repeating_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    service = load_service(monkeypatch)
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(service, '_bound_target', lambda submitted: target())
    monkeypatch.setattr(service, 'read_configmap', lambda selected: live_payload())
    monkeypatch.setattr(service, 'get_impact_context', lambda selected: impact())
    monkeypatch.setattr(
        service,
        'authorization_call',
        lambda *args, **kwargs: pytest.fail('Final delete must use the signed validation receipt.'),
    )

    api = SimpleNamespace(delete_namespaced_config_map=lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(service, 'live_call', lambda cluster, operation, callback: callback(api))

    result = service.delete_configmap(
        form(),
        validate_only=False,
        expected_resource_version='101',
    )

    assert len(calls) == 1
    assert calls[0]['name'] == 'application-config'
    assert calls[0]['namespace'] == 'default'
    assert calls[0]['body'].preconditions.resource_version == '101'
    assert result['operation'] == 'deletion'
    assert result['validation_mode'] == 'validated_receipt'


def test_final_delete_rejects_target_changed_after_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    service = load_service(monkeypatch)
    monkeypatch.setattr(service, '_bound_target', lambda submitted: target())
    monkeypatch.setattr(service, 'read_configmap', lambda selected: live_payload('102'))
    monkeypatch.setattr(service, 'get_impact_context', lambda selected: impact())

    with pytest.raises(ValueError, match='changed after validation'):
        service.delete_configmap(
            form(),
            validate_only=False,
            expected_resource_version='101',
        )



def entries(*, data=None, binary_data=None):
    data = data or {}
    binary_data = binary_data or {}
    return SimpleNamespace(
        data=data,
        binary_data=binary_data,
        key_names=sorted([*data, *binary_data]),
        payload_size_bytes=sum(len(key) + len(value) for key, value in data.items()),
    )


def test_create_validation_executes_one_server_side_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    service = load_service(monkeypatch)
    calls: list[dict[str, object]] = []
    selected_cluster = SimpleNamespace(id=7, name='Development')

    monkeypatch.setattr(service, '_cluster', lambda cluster_id: selected_cluster)
    monkeypatch.setattr(service, '_validate_namespace', lambda namespace, cluster_id: 'default')
    monkeypatch.setattr(service, 'parse_entries', lambda submitted: entries(binary_data={'asset.bin': 'aGVsbG8='}))
    monkeypatch.setattr(
        service,
        'live_call',
        lambda cluster, operation, callback: callback(
            SimpleNamespace(
                create_namespaced_config_map=lambda **kwargs: (
                    calls.append(kwargs)
                    or SimpleNamespace(metadata=SimpleNamespace(resource_version='201'))
                )
            )
        ),
    )

    metadata = service.create_configmap(
        {
            'cluster_id': '7',
            'namespace': 'default',
            'configmap_name': 'application-config',
            'immutable': 'true',
        },
        dry_run=True,
    )

    assert len(calls) == 1
    assert calls[0]['dry_run'] == 'All'
    assert calls[0]['body'].binary_data == {'asset.bin': 'aGVsbG8='}
    assert metadata['operation'] == 'validation'


def test_final_create_executes_one_dry_run_then_one_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    service = load_service(monkeypatch)
    calls: list[dict[str, object]] = []
    selected_cluster = SimpleNamespace(id=7, name='Development')

    monkeypatch.setattr(service, '_cluster', lambda cluster_id: selected_cluster)
    monkeypatch.setattr(service, '_validate_namespace', lambda namespace, cluster_id: 'default')
    monkeypatch.setattr(service, 'parse_entries', lambda submitted: entries(data={'feature': 'enabled'}))
    monkeypatch.setattr(
        service,
        'live_call',
        lambda cluster, operation, callback: callback(
            SimpleNamespace(
                create_namespaced_config_map=lambda **kwargs: (
                    calls.append(kwargs)
                    or SimpleNamespace(metadata=SimpleNamespace(resource_version='202'))
                )
            )
        ),
    )

    metadata = service.create_configmap(
        {
            'cluster_id': '7',
            'namespace': 'default',
            'configmap_name': 'application-config',
        },
        dry_run=False,
    )

    assert [call['dry_run'] for call in calls] == ['All', None]
    assert metadata['operation'] == 'creation'


def test_final_update_executes_one_dry_run_then_one_resource_version_bound_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = load_service(monkeypatch)
    calls: list[dict[str, object]] = []
    selected_target = target()
    proposed = entries(binary_data={'asset.bin': 'aGVsbG8='})

    monkeypatch.setattr(service, '_bound_target', lambda submitted: selected_target)
    monkeypatch.setattr(
        service,
        'read_configmap',
        lambda selected: {
            'data': {'feature': 'disabled'},
            'binary_data': {},
            'immutable': False,
            'resource_version': '301',
        },
    )
    monkeypatch.setattr(service, 'parse_entries', lambda submitted: proposed)
    monkeypatch.setattr(service, 'merge_entries', lambda existing, submitted, mode: proposed)
    monkeypatch.setattr(
        service,
        'diff_entries',
        lambda existing, submitted: {
            'added': ['asset.bin'],
            'changed': [],
            'removed': ['feature'],
            'unchanged': [],
        },
    )
    monkeypatch.setattr(service, 'get_impact_context', lambda selected: impact())
    monkeypatch.setattr(
        service,
        'live_call',
        lambda cluster, operation, callback: callback(
            SimpleNamespace(
                patch_namespaced_config_map=lambda **kwargs: (
                    calls.append(kwargs)
                    or SimpleNamespace(metadata=SimpleNamespace(resource_version='302'))
                )
            )
        ),
    )

    metadata = service.update_configmap(
        {'update_mode': 'replace', 'confirm_replace': 'yes'},
        dry_run=False,
    )

    assert [call['dry_run'] for call in calls] == ['All', None]
    assert calls[0]['body']['metadata']['resourceVersion'] == '301'
    assert calls[0]['body']['binaryData'] == {'asset.bin': 'aGVsbG8='}
    assert calls[0]['body']['data'] == {'feature': None}
    assert metadata['operation'] == 'update'
