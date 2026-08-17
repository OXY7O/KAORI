from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytestmark = pytest.mark.functional
ROOT = Path(__file__).resolve().parents[2]
RECEIPTS_PATH = ROOT / 'app/kubernetes/operations/secrets/receipts.py'


def load_receipts(monkeypatch: pytest.MonkeyPatch):
    flask = ModuleType('flask')
    flask.current_app = SimpleNamespace(config={'SECRET_KEY': 'test-secret-key'})
    monkeypatch.setitem(sys.modules, 'flask', flask)
    spec = importlib.util.spec_from_file_location('secret_receipts_under_test', RECEIPTS_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, 'secret_receipts_under_test', module)
    spec.loader.exec_module(module)
    return module


def metadata() -> dict[str, object]:
    return {
        'cluster_id': 7,
        'namespace': 'default',
        'secret_name': 'application-secret',
        'resource_version': '101',
    }


def test_receipt_is_bound_to_user_target_and_resource_version(monkeypatch: pytest.MonkeyPatch) -> None:
    receipts = load_receipts(monkeypatch)
    token = receipts.issue_delete_receipt(metadata(), user_id=1)
    receipt = receipts.verify_delete_receipt(
        token,
        user_id=1,
        cluster_id='7',
        namespace='default',
        secret_name='application-secret',
    )
    assert receipt.resource_version == '101'


@pytest.mark.parametrize(
    ('user_id', 'cluster_id', 'namespace', 'secret_name', 'message'),
    [
        (2, '7', 'default', 'application-secret', 'different KAORI user'),
        (1, '8', 'default', 'application-secret', 'selected Secret changed'),
        (1, '7', 'production', 'application-secret', 'selected Secret changed'),
        (1, '7', 'default', 'other-secret', 'selected Secret changed'),
    ],
)
def test_receipt_rejects_user_or_target_drift(
    monkeypatch: pytest.MonkeyPatch,
    user_id: int,
    cluster_id: str,
    namespace: str,
    secret_name: str,
    message: str,
) -> None:
    receipts = load_receipts(monkeypatch)
    token = receipts.issue_delete_receipt(metadata(), user_id=1)
    with pytest.raises(ValueError, match=message):
        receipts.verify_delete_receipt(
            token,
            user_id=user_id,
            cluster_id=cluster_id,
            namespace=namespace,
            secret_name=secret_name,
        )


def test_receipt_rejects_tampering(monkeypatch: pytest.MonkeyPatch) -> None:
    receipts = load_receipts(monkeypatch)
    token = receipts.issue_delete_receipt(metadata(), user_id=1)
    with pytest.raises(ValueError, match='invalid'):
        receipts.verify_delete_receipt(
            token + 'tampered',
            user_id=1,
            cluster_id='7',
            namespace='default',
            secret_name='application-secret',
        )
