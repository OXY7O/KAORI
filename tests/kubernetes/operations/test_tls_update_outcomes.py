from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from sqlalchemy.exc import SQLAlchemyError

pytestmark = pytest.mark.functional

ROOT = Path(__file__).resolve().parents[3]
UPDATES_PATH = ROOT / 'app/kubernetes/governance/tls_certificates/updates.py'


def _module(name: str, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module = ModuleType(name)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _load_updates(monkeypatch: pytest.MonkeyPatch, *, commit_error: bool = False):
    for name in (
        'app',
        'app.extensions',
        'app.extensions.db',
        'app.kubernetes.governance',
        'app.kubernetes.governance.tls_certificates',
        'app.kubernetes.governance.tls_certificates.certificate',
        'app.kubernetes.governance.tls_certificates.constants',
        'app.kubernetes.governance.tls_certificates.mutation',
        'app.kubernetes.governance.tls_certificates.sync_state',
        'app.platform_operations',
        'app.platform_operations.jobs',
        'app.platform_operations.jobs.policies',
        'app.platform_operations.jobs.policies.service',
        'app.models',
        'flask',
        'flask_login',
    ):
        _module(name, monkeypatch)

    logger = SimpleNamespace(exception=lambda *args, **kwargs: None)
    sys.modules['flask'].current_app = SimpleNamespace(config={}, logger=logger)
    sys.modules['flask_login'].current_user = SimpleNamespace(id=41)

    session = SimpleNamespace(
        added=[],
        rollbacks=0,
        add=lambda item: session.added.append(item),
        rollback=lambda: setattr(session, 'rollbacks', session.rollbacks + 1),
        get=lambda model, identifier: None,
    )
    commit_calls = {'count': 0}

    def commit() -> None:
        commit_calls['count'] += 1
        if commit_error:
            raise SQLAlchemyError('database unavailable')

    session.commit = commit
    sys.modules['app.extensions.db'].db = SimpleNamespace(session=session)

    parsed = SimpleNamespace(
        common_name='api.example.com',
        issuer='Example CA',
        serial_number='1234',
        fingerprint_sha256='new-fingerprint',
        dns_names=['api.example.com'],
        not_before=None,
        not_after=None,
        days_remaining=90,
        status='healthy',
        risk_level='normal',
    )
    validation = SimpleNamespace(is_valid=True, parsed_certificate=parsed, errors=[])
    certificate = sys.modules['app.kubernetes.governance.tls_certificates.certificate']
    certificate.find_uncovered_hosts = lambda hosts, candidate: []
    certificate.matching_certificate_pattern = lambda host, names, common_name: common_name
    certificate.validate_certificate_pair = lambda *args, **kwargs: validation
    certificate.validity_policy_from_config = lambda config: None

    constants = sys.modules['app.kubernetes.governance.tls_certificates.constants']
    constants.TLS_COLLECTION_COLLECTED = 'collected'
    constants.TLS_COVERAGE_FULL = 'full'
    constants.TLS_COVERAGE_NONE = 'none'
    constants.TLS_COVERAGE_NOT_REPORTED = 'not_reported'
    constants.TLS_COVERAGE_PARTIAL = 'partial'
    constants.TLS_COVERAGE_UNCOVERED = 'uncovered'

    sync_state = sys.modules['app.kubernetes.governance.tls_certificates.sync_state']
    sync_state.tls_sync_stale_after = lambda interval: timedelta(minutes=int(interval) + 90)
    sync_state.tls_sync_evidence_is_current = (
        lambda at, *, stale_after, now: at is not None and at <= now and now - at <= stale_after
    )
    sys.modules['app.platform_operations.jobs.policies.service'].get_or_create_job_policy = (
        lambda key: SimpleNamespace(interval_minutes=360)
    )

    mutation = sys.modules['app.kubernetes.governance.tls_certificates.mutation']
    mutation.patch_tls_secret = lambda record, cert, key: None
    mutation.read_uploaded_pair = lambda files: (b'certificate', b'private-key')

    class Event:
        pass

    class Inventory:
        query = SimpleNamespace(get=lambda certificate_id: None)
        id = SimpleNamespace(in_=lambda ids: ids)

    models = sys.modules['app.models']
    models.TLSCertificateCollectionState = type(
        'TLSCertificateCollectionState',
        (),
        {'query': SimpleNamespace(get=lambda cluster_id: None)},
    )
    original_get = session.get

    def get_with_collected_mapping(model, identifier):
        if model is models.TLSCertificateCollectionState:
            return _collected_state()
        return original_get(model, identifier)

    session.get = get_with_collected_mapping
    models.TLSCertificateInventory = Inventory
    models.TLSCertificateUpdateEvent = Event
    models.User = type('User', (), {})

    spec = importlib.util.spec_from_file_location('tls_updates_under_test', UPDATES_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, 'tls_updates_under_test', module)
    spec.loader.exec_module(module)
    module._test_session = session
    module._test_commit_calls = commit_calls
    return module


def _record(identifier: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        id=identifier,
        cluster_id='cluster-1',
        namespace='default',
        secret_name=f'api-{identifier}-tls',
        fingerprint_sha256='old-fingerprint',
        not_after=None,
        ingress_hosts=[],
        collected_at=datetime.now(UTC),
    )


def _collected_state(*, at: datetime | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        secret_collection_status='collected',
        ingress_mapping_status='collected',
        collected_at=at or datetime.now(UTC),
    )


def test_single_tls_update_reports_provider_failure_separately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = _load_updates(monkeypatch)
    record = _record()
    updates.db.session.get = lambda model, certificate_id: (
        record
        if model is updates.TLSCertificateInventory
        else _collected_state()
        if model is updates.TLSCertificateCollectionState
        else None
    )
    monkeypatch.setattr(
        updates,
        'patch_tls_secret',
        lambda target, cert, key: (_ for _ in ()).throw(RuntimeError('forbidden')),
    )

    result = updates.apply_certificate_update(1, {})

    assert result['status'] == 'failed'
    assert result['provider_updated'] is False
    assert result['persistence_confirmed'] is True
    assert updates._test_commit_calls['count'] == 1


def test_single_tls_provider_failure_reports_unconfirmed_failure_event_when_database_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = _load_updates(monkeypatch, commit_error=True)
    record = _record()
    updates.db.session.get = lambda model, certificate_id: (
        record
        if model is updates.TLSCertificateInventory
        else _collected_state()
        if model is updates.TLSCertificateCollectionState
        else None
    )
    monkeypatch.setattr(
        updates,
        'patch_tls_secret',
        lambda target, cert, key: (_ for _ in ()).throw(RuntimeError('forbidden')),
    )

    result = updates.apply_certificate_update(1, {})

    assert result['status'] == 'failed'
    assert result['provider_updated'] is False
    assert result['persistence_confirmed'] is False
    assert updates._test_session.rollbacks >= 2


def test_single_tls_update_warns_when_provider_succeeds_but_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = _load_updates(monkeypatch, commit_error=True)
    record = _record()
    updates.db.session.get = lambda model, certificate_id: (
        record
        if model is updates.TLSCertificateInventory
        else _collected_state()
        if model is updates.TLSCertificateCollectionState
        else None
    )
    provider_calls: list[int] = []
    monkeypatch.setattr(
        updates,
        'patch_tls_secret',
        lambda target, cert, key: provider_calls.append(target.id),
    )

    result = updates.apply_certificate_update(1, {})

    assert provider_calls == [1]
    assert result['status'] == 'warning'
    assert result['provider_updated'] is True
    assert result['persistence_confirmed'] is False
    assert 'Run TLS synchronization' in result['message']


def test_bulk_tls_update_converts_provider_successes_to_persistence_warnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = _load_updates(monkeypatch, commit_error=True)
    targets = [_record(1), _record(2)]
    query = SimpleNamespace(
        filter=lambda expression: SimpleNamespace(all=lambda: targets),
        get=lambda certificate_id: None,
    )
    updates.TLSCertificateInventory.query = query
    provider_calls: list[int] = []
    monkeypatch.setattr(
        updates,
        'patch_tls_secret',
        lambda target, cert, key: provider_calls.append(target.id),
    )

    result = updates.apply_bulk_update({}, [1, 2])

    assert provider_calls == [1, 2]
    assert result['status'] == 'warning'
    assert result['provider_updated_count'] == 2
    assert result['persistence_gap_count'] == 2
    assert result['failed_count'] == 0
    assert {item['status'] for item in result['results']} == {'warning'}


def test_single_tls_update_blocks_uncovered_host_before_provider_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = _load_updates(monkeypatch)
    record = _record()
    record.ingress_hosts = ['uncovered.example.org']
    updates.db.session.get = lambda model, identifier: (
        record if model is updates.TLSCertificateInventory else _collected_state()
    )
    monkeypatch.setattr(updates, 'find_uncovered_hosts', lambda hosts, cert: hosts)
    calls: list[int] = []
    monkeypatch.setattr(updates, 'patch_tls_secret', lambda target, cert, key: calls.append(target.id))

    result = updates.apply_certificate_update(record.id, {})

    assert calls == []
    assert result['status'] == 'failed'
    assert result['provider_updated'] is False
    assert 'does not cover' in result['message']


def test_bulk_tls_coverage_blocker_aborts_before_any_provider_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = _load_updates(monkeypatch)
    first, second = _record(1), _record(2)
    second.ingress_hosts = ['uncovered.example.org']
    updates.TLSCertificateInventory.query = SimpleNamespace(
        filter=lambda expression: SimpleNamespace(all=lambda: [first, second]),
        get=lambda certificate_id: None,
    )
    monkeypatch.setattr(updates, 'find_uncovered_hosts', lambda hosts, cert: hosts)
    calls: list[int] = []
    monkeypatch.setattr(updates, 'patch_tls_secret', lambda target, cert, key: calls.append(target.id))

    result = updates.apply_bulk_update({}, [1, 2])

    assert calls == []
    assert result['status'] == 'failed'
    assert result['provider_updated_count'] == 0
    assert len(result['errors']) == 1


def test_tls_update_blocks_unknown_ingress_mapping_without_provider_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = _load_updates(monkeypatch)
    record = _record()
    updates.db.session.get = lambda model, identifier: record if model is updates.TLSCertificateInventory else None
    calls: list[int] = []
    monkeypatch.setattr(updates, 'patch_tls_secret', lambda target, cert, key: calls.append(target.id))
    result = updates.apply_certificate_update(record.id, {})
    assert calls == []
    assert result['status'] == 'failed'
    assert 'Not Reported' in result['message']


def test_bulk_tls_rejects_missing_target_without_partial_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = _load_updates(monkeypatch)
    first = _record(1)
    updates.TLSCertificateInventory.query = SimpleNamespace(
        filter=lambda expression: SimpleNamespace(all=lambda: [first]),
        get=lambda certificate_id: None,
    )
    calls: list[int] = []
    monkeypatch.setattr(updates, 'patch_tls_secret', lambda target, cert, key: calls.append(target.id))
    result = updates.apply_bulk_update({}, [1, 2])
    assert calls == []
    assert result['status'] == 'failed'
    assert 'target set changed' in result['message']


def test_bulk_tls_rejects_duplicate_target_ids_without_provider_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = _load_updates(monkeypatch)
    calls: list[int] = []
    monkeypatch.setattr(updates, 'patch_tls_secret', lambda target, cert, key: calls.append(target.id))
    result = updates.apply_bulk_update({}, [1, 1])
    assert calls == []
    assert result['status'] == 'failed'


def test_single_tls_rejects_old_but_collected_ingress_mapping_without_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = _load_updates(monkeypatch)
    record = _record()
    stale = datetime.now(UTC) - timedelta(days=2)
    updates.db.session.get = lambda model, identifier: (
        record if model is updates.TLSCertificateInventory else _collected_state(at=stale)
    )
    calls: list[int] = []
    monkeypatch.setattr(updates, 'patch_tls_secret', lambda target, cert, key: calls.append(target.id))
    result = updates.apply_certificate_update(record.id, {})
    assert calls == []
    assert result['provider_updated'] is False
    assert 'stale' in result['message']


def test_bulk_tls_rejects_old_certificate_row_before_any_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = _load_updates(monkeypatch)
    first, second = _record(1), _record(2)
    second.collected_at = datetime.now(UTC) - timedelta(days=2)
    updates.TLSCertificateInventory.query = SimpleNamespace(
        filter=lambda expression: SimpleNamespace(all=lambda: [first, second]),
        get=lambda certificate_id: None,
    )
    calls: list[int] = []
    monkeypatch.setattr(updates, 'patch_tls_secret', lambda target, cert, key: calls.append(target.id))
    result = updates.apply_bulk_update({}, [1, 2])
    assert calls == []
    assert result['status'] == 'failed'
    assert result['provider_updated_count'] == 0
    assert 'stale' in result['errors'][0]


def test_tls_preview_rejects_failed_secret_collection_with_collected_ingress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    updates = _load_updates(monkeypatch)
    record = _record()
    updates.TLSCertificateInventory.query = SimpleNamespace(
        filter=lambda expression: SimpleNamespace(all=lambda: [record]),
    )
    updates.db.session.get = lambda model, identifier: SimpleNamespace(
        secret_collection_status='collection_failed', ingress_mapping_status='collected',
        collected_at=datetime.now(UTC),
    )
    result = updates.preview_uploaded_pair({}, [record.id])
    assert len(result['targets']) == 1
    assert result['targets'][0]['status'] == 'blocked'
    assert 'Not Reported' in result['targets'][0]['message']
