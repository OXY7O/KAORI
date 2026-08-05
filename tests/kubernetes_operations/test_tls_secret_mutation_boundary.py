from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[2]
MUTATION_PATH = ROOT / 'app/governance/tls_certificates/mutation.py'
COMMON_ROOT = ROOT / 'app/common'


def _module(name: str, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module = ModuleType(name)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _load(name: str, path: Path, monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def load_mutation(monkeypatch: pytest.MonkeyPatch):
    for name in (
        'app',
        'app.common',
        'app.extensions',
        'app.extensions.db',
        'app.governance',
        'app.governance.tls_certificates',
        'app.governance.tls_certificates.collector',
        'app.governance.tls_certificates.constants',
        'app.models',
    ):
        _module(name, monkeypatch)

    _load(
        'app.common.kubernetes_secrets',
        COMMON_ROOT / 'kubernetes_secrets.py',
        monkeypatch,
    )
    _load(
        'app.common.sensitive_uploads',
        COMMON_ROOT / 'sensitive_uploads.py',
        monkeypatch,
    )
    constants = sys.modules['app.governance.tls_certificates.constants']
    constants.TLS_CRT_KEY = 'tls.crt'
    constants.TLS_KEY_KEY = 'tls.key'
    constants.TLS_SECRET_TYPE = 'kubernetes.io/tls'
    collector = sys.modules['app.governance.tls_certificates.collector']
    collector.build_kubernetes_client = lambda cluster: None
    cluster_model = type('Cluster', (), {})
    sys.modules['app.models'].Cluster = cluster_model
    sys.modules['app.extensions.db'].db = SimpleNamespace(
        session=SimpleNamespace(get=lambda model, identifier: None),
    )
    return _load('tls_mutation_under_test', MUTATION_PATH, monkeypatch)


class Upload:
    def __init__(self, payload: bytes, filename: str):
        self.payload = payload
        self.filename = filename
        self.offset = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self.payload) - self.offset
        result = self.payload[self.offset:self.offset + size]
        self.offset += len(result)
        return result


def test_uploaded_pair_is_required_and_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    mutation = load_mutation(monkeypatch)

    cert, key = mutation.read_uploaded_pair(
        {
            'tls_crt_file': Upload(b'certificate', 'tls.crt'),
            'tls_key_file': Upload(b'private-key', 'tls.key'),
        }
    )
    assert cert == b'certificate'
    assert key == b'private-key'

    with pytest.raises(ValueError, match='1 MiB or smaller'):
        mutation.read_uploaded_pair(
            {
                'tls_crt_file': Upload(b'x' * (1024 * 1024 + 1), 'tls.crt'),
                'tls_key_file': Upload(b'private-key', 'tls.key'),
            }
        )


def test_tls_patch_rereads_live_target_and_runs_one_dry_run_then_one_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mutation = load_mutation(monkeypatch)
    cluster = SimpleNamespace(id='cluster-1')
    mutation.db.session.get = lambda model, cluster_id: cluster
    live = SimpleNamespace(
        type='kubernetes.io/tls',
        metadata=SimpleNamespace(resource_version='701'),
        data={'tls.key': 'private'},
        string_data=None,
    )
    responses: list[object] = []
    calls: list[dict[str, object]] = []

    def patch(**kwargs):
        calls.append(
            {
                **kwargs,
                'body': {
                    'metadata': dict(kwargs['body']['metadata']),
                    'type': kwargs['body']['type'],
                    'data': dict(kwargs['body']['data']),
                },
            }
        )
        response = SimpleNamespace(data={'tls.key': 'echoed'}, string_data=None)
        responses.append(response)
        return response

    api = SimpleNamespace(
        read_namespaced_secret=lambda **kwargs: live,
        patch_namespaced_secret=patch,
    )
    monkeypatch.setattr(
        mutation,
        'build_kubernetes_client',
        lambda selected: SimpleNamespace(core_api=lambda: api),
    )

    version = mutation.patch_tls_secret(
        SimpleNamespace(cluster_id='cluster-1', namespace='default', secret_name='api-tls'),
        b'certificate',
        b'private-key',
    )

    assert version == '701'
    assert [call['dry_run'] for call in calls] == ['All', None]
    assert all(call['body']['metadata']['resourceVersion'] == '701' for call in calls)
    assert all(call['body']['type'] == 'kubernetes.io/tls' for call in calls)
    assert all(set(call['body']['data']) == {'tls.crt', 'tls.key'} for call in calls)
    assert live.data is None
    assert all(response.data is None for response in responses)


def test_tls_patch_rejects_live_type_drift_before_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    mutation = load_mutation(monkeypatch)
    mutation.db.session.get = lambda model, cluster_id: SimpleNamespace(id=cluster_id)
    calls: list[object] = []
    api = SimpleNamespace(
        read_namespaced_secret=lambda **kwargs: SimpleNamespace(
            type='Opaque',
            metadata=SimpleNamespace(resource_version='701'),
            data={},
            string_data=None,
        ),
        patch_namespaced_secret=lambda **kwargs: calls.append(kwargs),
    )
    monkeypatch.setattr(
        mutation,
        'build_kubernetes_client',
        lambda selected: SimpleNamespace(core_api=lambda: api),
    )

    with pytest.raises(ValueError, match='no longer a TLS Secret'):
        mutation.patch_tls_secret(
            SimpleNamespace(cluster_id='cluster-1', namespace='default', secret_name='api-tls'),
            b'certificate',
            b'private-key',
        )
    assert calls == []
