"""SC-03 webhook maintenance is opt-in, bounded and backed by JobExecution."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask

from app.integrations.source_control import webhook_maintenance
from app.integrations.source_control.source_control.providers.github import webhook_recovery


class StubSession:
    def __init__(self, rows):
        self.rows = {row.id: row for row in rows}
        self.rollbacks = 0

    def scalars(self, _statement):
        return list(self.rows)

    def get(self, _model, identity):
        return self.rows.get(identity)

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture
def admitted(monkeypatch):
    monkeypatch.setattr(
        webhook_recovery, 'provider_kind',
        lambda *_: SimpleNamespace(available=True),
    )


def _delivery(identity, state):
    return SimpleNamespace(id=identity, processing_state=state)


def test_provider_planned_must_not_query_database(monkeypatch):
    monkeypatch.setattr(
        webhook_recovery, 'provider_kind',
        lambda *_: SimpleNamespace(available=False),
    )
    class NoQuery:
        def scalars(self, _):
            pytest.fail('Planned provider cannot read work queue')

    result = webhook_recovery.recover_webhook_inbox(NoQuery())
    assert result['status'] == 'not_admitted'
    assert result['examined'] == 0


def test_recovery_uses_only_bounded_delivery_records(admitted, monkeypatch):
    session = StubSession([
        _delivery(1, 'received'), _delivery(2, 'queued'),
        _delivery(3, 'dispatching'),
    ])
    calls = []
    monkeypatch.setattr(
        webhook_recovery, 'dispatch_committed_delivery',
        lambda *_args, **kw: (
            calls.append(('dispatch', kw['delivery_record_id']))
            or SimpleNamespace(state='queued')
        ),
    )
    monkeypatch.setattr(
        webhook_recovery, 'reconcile_delivery_completion',
        lambda *_args, **kw: (
            calls.append(('reconcile', kw['delivery_record_id']))
            or 'reconciled_success'
        ),
    )
    monkeypatch.setattr(
        webhook_recovery, 'flag_abandoned_dispatch',
        lambda *_args, **kw: calls.append(('abandoned', kw['delivery_record_id'])) or True,
    )
    result = webhook_recovery.recover_webhook_inbox(session)
    assert calls == [('dispatch', 1), ('reconcile', 2), ('abandoned', 3)]
    assert result == {
        'status': 'processed', 'examined': 3, 'queued': 1,
        'reconciled': 1, 'uncertain': 1, 'failed': 0,
    }


def test_one_bad_delivery_does_not_abort_other_recovery(admitted, monkeypatch):
    session = StubSession([_delivery(1, 'received'), _delivery(2, 'received')])
    def dispatch(_session, *, delivery_record_id):
        if delivery_record_id == 1:
            raise RuntimeError('unsafe provider error')
        return SimpleNamespace(state='queued')
    monkeypatch.setattr(webhook_recovery, 'dispatch_committed_delivery', dispatch)
    outcome = webhook_recovery.recover_webhook_inbox(session)
    assert outcome['failed'] == 1
    assert outcome['queued'] == 1
    assert session.rollbacks == 1


@pytest.mark.parametrize('limit', [0, -1, True, 26])
def test_recovery_batch_is_never_unbounded(limit):
    with pytest.raises(ValueError, match='between 1 and 25'):
        webhook_recovery.recover_webhook_inbox(StubSession([]), limit=limit)


def test_disabled_default_worker_does_not_consume_inbox(monkeypatch):
    app = Flask(__name__)
    app.config['SOURCE_CONTROL_WEBHOOK_CONSUMER_ENABLED'] = False
    monkeypatch.setattr(
        webhook_maintenance, 'recover_webhook_inbox',
        lambda *_args: pytest.fail('Disabled worker must not process deliveries'),
    )
    with app.app_context():
        outcome = webhook_maintenance.recover_signed_deliveries.run()
    assert outcome['status'] == 'disabled'
    assert outcome['examined'] == 0


def test_sweep_only_selects_due_retry_and_terminal_jobs():
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2] /
        'app/integrations/source_control/source_control/providers/github/webhook_recovery.py'
    ).read_text()
    assert "SourceWebhookDelivery.last_attempt_at <= now - timedelta(minutes=5)" in src
    assert "SourceWebhookDelivery.last_attempt_at <= now - timedelta(minutes=20)" in src
    assert "JobExecution.status.in_(TERMINAL_JOB_STATUSES)" in src
    assert "JobExecution.id.is_(None)" in src
    assert "SourceWebhookDelivery.processing_state == 'received'" in src


def test_no_external_route_or_raw_credentials_in_recovery():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    src = root.joinpath(
        'app/integrations/source_control/source_control/providers/github/webhook_recovery.py'
    ).read_text()
    worker = root.joinpath('app/integrations/source_control/webhook_maintenance.py').read_text()
    assert '@shared_task' not in src
    assert 'Blueprint(' not in src
    assert 'app.integrations.source_control.webhook_maintenance.recover_signed_deliveries' in worker
    assert 'SOURCE_CONTROL_WEBHOOK_CONSUMER_ENABLED' in worker
    assert 'log.exception' not in src
    assert 'apply_async(' not in src
