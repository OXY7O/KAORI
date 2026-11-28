"""Local review diagnostics are read-only and never fabricate receipt authority."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from flask import Flask

from app.commands import automation_remote_review as command
from app.infrastructure_automation import remote_preflight_target as target_service
from app.infrastructure_automation.kubernetes.source_policy import SOURCE_CANDIDATE_SHA
from app.infrastructure_automation.remote_preflight_source import REMOTE_CANDIDATE_SHA, RemoteSourceReview
from app.infrastructure_automation.remote_worker_review import WorkerReviewEvidence


@pytest.fixture
def diagnostic(monkeypatch):
    app = Flask(__name__)
    app.cli.add_command(command.automation_remote_review_check)
    events = []
    target = target_service.RemoteTargetReview(
        31, 7, SOURCE_CANDIDATE_SHA, 'sha256:' + 'a' * 64, 'b' * 64, 'c' * 64, 'd' * 64,
        (), datetime.now(UTC) + timedelta(minutes=10),
    )
    monkeypatch.setattr(command, 'review_enabled', lambda: True)
    monkeypatch.setattr(command, 'begin_security_review_transaction', lambda: events.append('begin'))
    monkeypatch.setattr(command, 'lock_explicit_permissions', lambda *args: True)
    monkeypatch.setattr(command, 'db', SimpleNamespace(session=SimpleNamespace(rollback=lambda: events.append('rollback'))))
    monkeypatch.setattr(command, 'diagnose_remote_preflight_target', lambda **kwargs: ('historical_target_qualified', target))
    monkeypatch.setenv('KAORI_LOCAL_REMOTE_REVIEW_WORKER', 'automation@fixture')
    monkeypatch.setenv('KAORI_LOCAL_REMOTE_REVIEW_SOURCE', '/fixture/source')

    def source(path):
        assert events[-1] == 'rollback'
        events.append('source')
        return RemoteSourceReview(REMOTE_CANDIDATE_SHA, 'e' * 64)

    monkeypatch.setattr(command, 'review_remote_source_candidate', source)
    monkeypatch.setattr(
        command, 'resolve_remote_worker_review',
        lambda *args, **kwargs: WorkerReviewEvidence('f' * 64, datetime.now(UTC) + timedelta(minutes=5)),
    )
    return app.test_cli_runner(), events


def _invoke(runner, *extra):
    return runner.invoke(args=['automation-remote-review-check', '--connection-id', '31', '--actor-id', '7', *extra])


def test_target_only_rolls_back_without_worker_check(diagnostic):
    runner, events = diagnostic
    result = _invoke(runner)
    assert result.exit_code == 0
    assert 'target_status=historical_target_qualified' in result.output
    assert 'configured_worker_review=not_checked' in result.output
    assert 'execution_authorized=false' in result.output
    assert events == ['begin', 'rollback']


def test_signed_worker_check_never_claims_runtime_attestation(diagnostic):
    runner, events = diagnostic
    result = _invoke(runner, '--worker-check')
    assert result.exit_code == 0
    assert 'remote_source=disabled_candidate_checked' in result.output
    assert 'configured_worker_review=historical_receipt_qualified' in result.output
    assert 'runtime_attestation_verified=false' in result.output
    assert 'execution_authorized=false' in result.output
    assert '/fixture/source' not in result.output
    assert events == ['begin', 'rollback', 'source']


@pytest.mark.parametrize('failure,reason', [
    ('disabled', 'local_review_disabled'),
    ('actor', 'actor_permissions_unqualified'),
    ('target', 'inventory_receipt_unqualified'),
    ('worker', 'signed_worker_review_unqualified'),
])
def test_first_blocker_returns_nonzero(diagnostic, monkeypatch, failure, reason):
    runner, events = diagnostic
    if failure == 'disabled':
        monkeypatch.setattr(command, 'review_enabled', lambda: False)
    elif failure == 'actor':
        monkeypatch.setattr(command, 'lock_explicit_permissions', lambda *args: False)
    elif failure == 'target':
        monkeypatch.setattr(command, 'diagnose_remote_preflight_target', lambda **kwargs: (reason, None))
    else:
        monkeypatch.setattr(command, 'resolve_remote_worker_review', lambda *args, **kwargs: None)
    result = _invoke(runner, '--worker-check')
    assert result.exit_code != 0
    assert reason in result.output
    assert 'execution_authorized=false' in result.output
    assert events == ([] if failure == 'disabled' else ['begin', 'rollback', 'source'] if failure == 'worker' else ['begin', 'rollback'])


@pytest.fixture
def target_records(monkeypatch):
    now = datetime.now(UTC)
    connection = SimpleNamespace(
        enabled=True, integration_type='configuration_automation', provider_key='ansible', lifecycle_status='active',
        metadata_json={'source_sha': SOURCE_CANDIDATE_SHA, 'execution_environment_digest': 'sha256:' + 'a' * 64},
    )
    assignments = [
        SimpleNamespace(id=index, host_id=f'fixture-{index}', role='control_plane' if index == 1 else 'worker',
                        host=SimpleNamespace(address=f'10.0.0.{index}'))
        for index in range(1, 4)
    ]
    preview = SimpleNamespace(inventory_fingerprint='b' * 64, host_count=3)
    receipt = SimpleNamespace(state='historical_aligned', parser_verified=True, fingerprint='c' * 64)
    access = SimpleNamespace(fingerprint='d' * 64, expires_at=now + timedelta(minutes=5), execution_authorized=False)
    monkeypatch.setattr(target_service, 'db', SimpleNamespace(session=SimpleNamespace(
        get=lambda *args, **kwargs: connection,
        execute=lambda statement: SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: assignments)),
        refresh=lambda *args, **kwargs: None,
    )))
    monkeypatch.setattr(target_service, 'committed_source_state', lambda metadata: 'checked')
    monkeypatch.setattr(target_service, 'preview_inventory_intent', lambda *args: preview)
    monkeypatch.setattr(target_service, 'committed_inventory_receipt_review', lambda *args: receipt)
    monkeypatch.setattr(target_service, 'review_remote_access_evidence', lambda **kwargs: access)
    return connection, assignments, preview, receipt, access, now


@pytest.mark.parametrize('failure,state', [
    (None, 'historical_target_qualified'), ('connection', 'connection_unqualified'),
    ('source', 'source_not_checked'), ('ee', 'ee_digest_unqualified'), ('topology', 'topology_unqualified'),
    ('registry', 'host_registry_unqualified'), ('inventory', 'inventory_receipt_unqualified'),
    ('access', 'access_review_unqualified'),
])
def test_diagnostics_reuse_actual_target_gate(target_records, failure, state):
    connection, assignments, preview, receipt, access, now = target_records
    if failure == 'connection':
        connection.enabled = False
    elif failure == 'source':
        connection.metadata_json = None
    elif failure == 'ee':
        connection.metadata_json['execution_environment_digest'] = 'unknown'
    elif failure == 'topology':
        assignments.pop()
    elif failure == 'registry':
        preview.inventory_fingerprint = None
    elif failure == 'inventory':
        receipt.parser_verified = False
    elif failure == 'access':
        access.expires_at = now
    kwargs = {'actor_id': 7, 'connection_id': 31, 'now': now}
    actual, target = target_service.diagnose_remote_preflight_target(**kwargs)
    assert actual == state
    assert target_service.review_remote_preflight_target(**kwargs) == target
    if failure is None:
        assert target is not None and target.execution_authorized is False
    else:
        assert target is None
