from __future__ import annotations

import importlib.util
import sys
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[2]
SECRET_ROOT = ROOT / 'app/kubernetes_operations/secrets'


def _module(name: str, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module = ModuleType(name)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _value_type(name: str):
    class Value:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    Value.__name__ = name
    return Value


def _load_file(name: str, path: Path, monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def _install_base_modules(monkeypatch: pytest.MonkeyPatch) -> dict[str, ModuleType]:
    names = (
        'app',
        'app.common',
        'app.governance',
        'app.governance.tls_certificates',
        'app.governance.tls_certificates.certificate',
        'app.integrations',
        'app.integrations.kubernetes',
        'app.integrations.kubernetes.resolver',
        'app.integrations.kubernetes.tls',
        'app.kubernetes_operations',
        'app.kubernetes_operations.secrets',
        'app.kubernetes_operations.secrets.live_service',
        'app.kubernetes_operations.secrets.impact',
        'app.models',
        'kubernetes',
        'kubernetes.client',
        'kubernetes.client.exceptions',
        'kubernetes.config',
        'kubernetes.config.config_exception',
    )
    modules = {name: _module(name, monkeypatch) for name in names}

    _load_file(
        'app.common.sensitive_uploads',
        ROOT / 'app/common/sensitive_uploads.py',
        monkeypatch,
    )
    _load_file(
        'app.common.kubernetes_secrets',
        ROOT / 'app/common/kubernetes_secrets.py',
        monkeypatch,
    )

    contracts = _load_file(
        'app.kubernetes_operations.secrets.contracts',
        SECRET_ROOT / 'contracts.py',
        monkeypatch,
    )
    validation = _load_file(
        'app.kubernetes_operations.secrets.validation',
        SECRET_ROOT / 'validation.py',
        monkeypatch,
    )
    modules['contracts'] = contracts
    modules['validation'] = validation

    modules['app.integrations.kubernetes.resolver'].tls_policy_for_cluster = lambda cluster: (None, False)
    modules['app.integrations.kubernetes.tls'].weak_tls_context = lambda **kwargs: nullcontext()
    modules['app.governance.tls_certificates.certificate'].validate_certificate_pair = lambda *args: None

    class ApiException(Exception):
        def __init__(self, status=None, reason=''):
            super().__init__(status)
            self.status = status
            self.reason = reason

    class ConfigException(Exception):
        pass

    modules['kubernetes.client.exceptions'].ApiException = ApiException
    modules['kubernetes.config.config_exception'].ConfigException = ConfigException

    client = modules['kubernetes.client']
    for name in (
        'V1ObjectMeta',
        'V1Secret',
        'V1DeleteOptions',
        'V1Preconditions',
        'V1SelfSubjectAccessReview',
        'V1SelfSubjectAccessReviewSpec',
        'V1ResourceAttributes',
    ):
        setattr(client, name, _value_type(name))
    modules['kubernetes'].client = client

    live = modules['app.kubernetes_operations.secrets.live_service']
    live.LiveSecretSnapshot = type('LiveSecretSnapshot', (), {})
    live.core_api = lambda cluster: None
    live.authorization_api = lambda cluster: None
    live.get_cluster = lambda cluster_id: None
    live.list_live_namespaces = lambda cluster_id: []
    live.list_live_secrets = lambda *args, **kwargs: []
    live.read_live_secret = lambda *args, **kwargs: None
    live.scrub_secret_payload = lambda secret: (
        (setattr(secret, 'data', None), setattr(secret, 'string_data', None)) if secret is not None else None
    )
    live.verify_live_namespace = lambda cluster, namespace: None

    modules['app.kubernetes_operations.secrets.impact'].get_secret_impact_context = lambda target: (
        contracts.SecretImpactContext(
            items=[],
            collection_state='Collected',
            reported=True,
        )
    )
    modules['app.models'].Cluster = type('Cluster', (), {})
    return modules


def _target(resource_version: str = '101') -> SimpleNamespace:
    return SimpleNamespace(
        cluster=SimpleNamespace(id=7, name='Development'),
        cluster_id='7',
        cluster_name='Development',
        namespace='default',
        name='application-secret',
        secret_type='Opaque',
        immutable=False,
        key_names=('username', 'password'),
        key_count=2,
        resource_version=resource_version,
    )


def _delete_form() -> dict[str, str]:
    return {
        'cluster_id': '7',
        'namespace': 'default',
        'secret_name': 'application-secret',
        'target_cluster_id': '7',
        'target_namespace': 'default',
        'target_secret_name': 'application-secret',
        'confirm_name': 'application-secret',
    }


class _Form(dict):
    def getlist(self, key: str) -> list[str]:
        value = self.get(key, [])
        return list(value) if isinstance(value, (list, tuple)) else [value]


def test_create_service_executes_exactly_one_provider_call_per_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _load_file('secret_create_under_test', SECRET_ROOT / 'create_service.py', monkeypatch)
    calls: list[dict[str, object]] = []
    cluster = SimpleNamespace(id=7, name='Development')
    responses: list[object] = []

    def create_secret(**kwargs):
        calls.append(kwargs)
        response = SimpleNamespace(
            metadata=SimpleNamespace(uid='uid-1', resource_version='201'),
            data={'password': 'echoed'},
            string_data={'password': 'echoed'},
        )
        responses.append(response)
        return response

    api = SimpleNamespace(create_namespaced_secret=create_secret)
    monkeypatch.setattr(service, 'get_cluster', lambda cluster_id: cluster)
    monkeypatch.setattr(service, 'verify_live_namespace', lambda selected, namespace: None)
    monkeypatch.setattr(service, 'core_api', lambda selected: api)

    submitted = _Form(
        cluster_id='7',
        namespace='default',
        secret_name='application-secret',
        secret_type='opaque',
        immutable='false',
        generic_key=['username'],
        generic_value=['operator'],
    )
    validation = service.execute_secret_operation(submitted, {}, dry_run=True)
    mutation = service.execute_secret_operation(submitted, {}, dry_run=False)

    assert [call['dry_run'] for call in calls] == ['All', None]
    assert validation.metadata['operation'] == 'validation'
    assert mutation.metadata['operation'] == 'creation'
    assert calls[0]['body'].string_data is None
    assert calls[1]['body'].string_data is None
    assert all(response.data is None for response in responses)
    assert all(response.string_data is None for response in responses)


def test_replace_service_executes_exactly_one_resource_version_bound_patch_per_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_base_modules(monkeypatch)
    payloads = _module('app.kubernetes_operations.secrets.replace_payloads', monkeypatch)
    payloads.build_replace_patch = lambda form, files, target: {'username': 'new-user'}
    service = _load_file('secret_replace_under_test', SECRET_ROOT / 'replace_service.py', monkeypatch)
    calls: list[dict[str, object]] = []
    target = _target()
    api = SimpleNamespace(
        patch_namespaced_secret=lambda **kwargs: (
            calls.append(kwargs) or SimpleNamespace(close=lambda: None, release_conn=lambda: None)
        )
    )
    monkeypatch.setattr(service, '_bound_target', lambda form: target)
    monkeypatch.setattr(service, 'core_api', lambda cluster: api)

    validation = service.execute_secret_replacement({}, {}, dry_run=True)
    mutation = service.execute_secret_replacement({'confirm_replace': 'yes'}, {}, dry_run=False)

    assert [call['dry_run'] for call in calls] == ['All', None]
    assert all(call['body']['metadata']['resourceVersion'] == '101' for call in calls)
    assert all(call['body']['data'] is None for call in calls)
    assert validation.metadata['operation'] == 'validation'
    assert mutation.metadata['operation'] == 'replacement'


def test_delete_validation_uses_one_non_destructive_authorization_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_base_modules(monkeypatch)
    service = _load_file('secret_delete_under_test', SECRET_ROOT / 'delete_service.py', monkeypatch)
    target = _target()
    reviews: list[object] = []
    authorization = SimpleNamespace(
        create_self_subject_access_review=lambda **kwargs: (
            reviews.append(kwargs['body']) or SimpleNamespace(status=SimpleNamespace(allowed=True))
        )
    )
    monkeypatch.setattr(service, '_bound_target', lambda form: target)
    monkeypatch.setattr(service, 'authorization_api', lambda cluster: authorization)
    monkeypatch.setattr(
        service,
        'core_api',
        lambda cluster: pytest.fail('Validation must not construct or call the Secret DELETE endpoint.'),
    )

    result = service.execute_secret_deletion(_delete_form(), validate_only=True)

    assert len(reviews) == 1
    attributes = reviews[0].spec.resource_attributes
    assert attributes.resource == 'secrets'
    assert attributes.verb == 'delete'
    assert attributes.namespace == 'default'
    assert attributes.name == 'application-secret'
    assert result.metadata['validation_mode'] == 'authorization_preflight'


def test_final_delete_executes_once_with_validated_resource_version(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_base_modules(monkeypatch)
    service = _load_file('secret_delete_under_test', SECRET_ROOT / 'delete_service.py', monkeypatch)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(service, '_bound_target', lambda form: _target())
    monkeypatch.setattr(
        service,
        '_validate_delete_authorization',
        lambda target: pytest.fail('Final delete must rely on the signed receipt.'),
    )
    monkeypatch.setattr(
        service,
        'core_api',
        lambda cluster: SimpleNamespace(delete_namespaced_secret=lambda **kwargs: calls.append(kwargs)),
    )

    result = service.execute_secret_deletion(
        _delete_form(),
        validate_only=False,
        expected_resource_version='101',
    )

    assert len(calls) == 1
    assert calls[0]['body'].preconditions.resource_version == '101'
    assert result.metadata['validation_mode'] == 'validated_receipt'


def test_final_delete_rejects_resource_version_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_base_modules(monkeypatch)
    service = _load_file('secret_delete_under_test', SECRET_ROOT / 'delete_service.py', monkeypatch)
    monkeypatch.setattr(service, '_bound_target', lambda form: _target('102'))

    with pytest.raises(ValueError, match='changed after validation'):
        service.execute_secret_deletion(
            _delete_form(),
            validate_only=False,
            expected_resource_version='101',
        )


def test_signed_delete_receipt_is_user_target_and_resource_version_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flask = _module('flask', monkeypatch)
    flask.current_app = SimpleNamespace(config={'SECRET_KEY': 'test-secret-key'})
    receipts = _load_file('secret_receipts_under_test', SECRET_ROOT / 'receipts.py', monkeypatch)

    token = receipts.issue_delete_receipt(
        {
            'cluster_id': '7',
            'namespace': 'default',
            'secret_name': 'application-secret',
            'resource_version': '101',
        },
        user_id=11,
    )
    receipt = receipts.verify_delete_receipt(
        token,
        user_id=11,
        cluster_id='7',
        namespace='default',
        secret_name='application-secret',
    )
    assert receipt.resource_version == '101'

    with pytest.raises(ValueError, match='different KAORI user'):
        receipts.verify_delete_receipt(
            token,
            user_id=12,
            cluster_id='7',
            namespace='default',
            secret_name='application-secret',
        )
    with pytest.raises(ValueError, match='selected Secret changed'):
        receipts.verify_delete_receipt(
            token,
            user_id=11,
            cluster_id='7',
            namespace='default',
            secret_name='different-secret',
        )
    with pytest.raises(ValueError, match='invalid'):
        receipts.verify_delete_receipt(
            f'{token}tampered',
            user_id=11,
            cluster_id='7',
            namespace='default',
            secret_name='application-secret',
        )
