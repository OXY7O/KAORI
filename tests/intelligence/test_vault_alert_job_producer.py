"""Manual-only Vault Alertmanager producer uses canonical jobs and sanitized evidence."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from flask import Flask

from app.extensions.db import db
from app.intelligence.alert_signals import vault_jobs
from app.intelligence.alert_signals.vault_source import read_vault_alert_observations
from app.models.alert_signal import AlertSignalSnapshot
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.platform_operations.jobs.registry import get_job_definition

KEY = bytes.fromhex('0c' * 32)


@pytest.fixture
def store():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='test-only',
        SQLALCHEMY_DATABASE_URI='sqlite://',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    with app.app_context():
        tables = [
            IntegrationInstance.__table__,
            IntegrationBinding.__table__,
            AlertmanagerInstance.__table__,
            AlertSignalSnapshot.__table__,
        ]
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        try:
            yield
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _instance(kind, provider):
    identity = IntegrationInstance(
        integration_type=kind,
        provider_key=provider,
        adapter_key='test',
        name=f'{kind}-{IntegrationInstance.query.count()}',
        enabled=True,
        lifecycle_status='active',
        readiness_status='ready',
    )
    db.session.add(identity)
    db.session.flush()
    return identity


def _source():
    vault = _instance('secrets_pki', 'vault')
    source = _instance('alert_source', 'alertmanager')
    provider = AlertmanagerInstance(
        integration_instance_id=source.id,
        endpoint='https://alertmanager.example.invalid',
        verify_ssl=True,
    )
    db.session.add(provider)
    binding = IntegrationBinding(
        integration_instance_id=source.id,
        asset_type='vault_instance',
        asset_key=str(vault.id),
        enabled=True,
        validation_profile='vault-alerts-v1',
        validation_status='ready',
        selector_json={
            'matchers': [{'label': 'vault_instance', 'operator': '=', 'value': str(vault.id)}],
        },
        validation_evidence={
            'profile_key': 'vault-alerts-v1',
            'vault_alert_sample': {'status': 'qualified'},
        },
        last_validated_at=datetime.now(UTC),
    )
    db.session.add(binding)
    db.session.commit()
    return vault, source, provider, binding


def _alert(vault_id):
    return {
        'labels': {
            'vault_instance': str(vault_id),
            'severity': 'critical',
            'alertname': 'PRIVATE/SECRET/PATH',
        },
        'annotations': {'summary': 'PRIVATE/SECRET/PATH'},
        'status': {'state': 'active'},
        'fingerprint': 'aabbccddeeff1234',
        'startsAt': (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
    }


def test_job_catalog_is_existing_manual_only_configuration():
    definition = get_job_definition('secrets_pki.vault_alerts.observe')
    assert definition.schedule_supported is False
    assert definition.default_enabled is False
    assert definition.manual_execution_supported is True
    assert definition.queue_name == 'inventory'
    assert definition.execute_permission == 'jobs.execute'
    assert definition.domain_execute_permission == 'secrets_pki.sync'
    assert definition.dispatcher_path == (
        'app.intelligence.alert_signals.vault_jobs:dispatch_vault_alert_observations'
    )


def test_eligible_target_list_is_only_exact_vault_binding(store):
    vault, _source_identity, _provider, binding = _source()
    assert vault_jobs.build_vault_alert_observation_targets() == [binding.id]
    binding.selector_json = {'matchers': [{'label': 'job', 'operator': '=', 'value': 'other'}]}
    db.session.commit()
    assert vault_jobs.build_vault_alert_observation_targets() == []
    assert vault.id > 0


def test_disabled_provider_binding_and_duplicate_source_never_dispatch(store):
    vault, source, _provider, binding = _source()
    source.enabled = False
    db.session.commit()
    assert vault_jobs.build_vault_alert_observation_targets() == []
    source.enabled = True
    binding.enabled = False
    db.session.commit()
    assert vault_jobs.build_vault_alert_observation_targets() == []
    binding.enabled = True
    second_source = _instance('alert_source', 'alertmanager')
    db.session.add(AlertmanagerInstance(
        integration_instance_id=second_source.id,
        endpoint='https://other.example.invalid',
    ))
    db.session.add(IntegrationBinding(
        integration_instance_id=second_source.id,
        asset_type='vault_instance',
        asset_key=str(vault.id),
        enabled=True,
    ))
    db.session.commit()
    assert vault_jobs.build_vault_alert_observation_targets() == []


def test_missing_alertmanager_provider_blocks_scope(store):
    _vault, _source_identity, provider, _binding = _source()
    db.session.delete(provider)
    db.session.commit()
    assert vault_jobs.build_vault_alert_observation_targets() == []


def test_dispatch_is_manual_only_and_deduplicated_via_canonical_admission(monkeypatch):
    calls = []
    monkeypatch.setattr(vault_jobs, 'build_vault_alert_observation_targets', lambda: [41])
    monkeypatch.setattr(
        vault_jobs,
        'enqueue_canonical_job',
        lambda **kw: (calls.append(kw) or SimpleNamespace(id=17), True),
    )
    blocked = vault_jobs.dispatch_vault_alert_observations(
        requested_by_user_id=3, trigger_type='scheduled',
    )
    assert blocked.status == 'blocked'
    assert not calls
    result = vault_jobs.dispatch_vault_alert_observations(
        requested_by_user_id=3, trigger_type='manual',
    )
    assert result.status == 'queued'
    assert result.created is True
    assert len(calls) == 1
    job = calls[0]
    assert job['task_kwargs'] == {'binding_ids': [41]}
    assert job['dispatch_options'].require_registered_worker is True
    assert job['scope_type'] == 'secrets_pki_alert_fleet'
    assert job['max_attempts'] == 1
    assert 'key' not in repr(job).lower()
    assert 'PRIVATE' not in repr(job)


@pytest.mark.parametrize('secret', [
    '',
    'deadbeef',
    'not-even-hex-' + 'a' * 64,
    'a' * 63,
    'a' * 129,
])
def test_worker_correlation_secret_is_fail_closed(monkeypatch, secret):
    monkeypatch.setenv('KAORI_VAULT_ALERT_CORRELATION_HMAC_KEY_HEX', secret)
    assert vault_jobs._worker_key() is None


def test_worker_key_requires_approved_hex_only(monkeypatch):
    monkeypatch.setenv('KAORI_VAULT_ALERT_CORRELATION_HMAC_KEY_HEX', 'ca' * 32)
    assert vault_jobs._worker_key() == bytes.fromhex('ca' * 32)


def test_provider_response_commits_only_opaque_evidence(store, monkeypatch):
    vault, _source_identity, _provider, binding = _source()
    filters_seen = []
    monkeypatch.setattr(vault_jobs, 'build_client', lambda _provider: SimpleNamespace(
        get_alerts=lambda **kwargs: (filters_seen.append(kwargs['filters']) or [_alert(vault.id)]),
    ))
    output = vault_jobs.observe_vault_alert_binding(binding.id, key=KEY)
    assert output == 'qualified'
    assert filters_seen == [[f'vault_instance="{vault.id}"']]
    result = read_vault_alert_observations(binding_id=binding.id)
    assert result['state'] == 'fresh'
    assert len(result['entries'][0]['handle']) == 64
    snapshot = AlertSignalSnapshot.query.one()
    snapshot_text = repr(snapshot.payload_json)
    for secret in ('PRIVATE/SECRET/PATH', 'aabbccddeeff1234', 'annotations', 'labels'):
        assert secret not in snapshot_text


def test_provider_failure_invalidates_previous_source_without_raw_error(store, monkeypatch):
    vault, _source_identity, _provider, binding = _source()
    monkeypatch.setattr(vault_jobs, 'build_client', lambda _provider: SimpleNamespace(
        get_alerts=lambda **_kw: [_alert(vault.id)],
    ))
    assert vault_jobs.observe_vault_alert_binding(binding.id, key=KEY) == 'qualified'

    def denied(**_kwargs):
        raise RuntimeError('PRIVATE/SECRET/PATH token://credential')

    monkeypatch.setattr(vault_jobs, 'build_client', lambda _provider: SimpleNamespace(
        get_alerts=denied,
    ))
    assert vault_jobs.observe_vault_alert_binding(binding.id, key=KEY) == 'unavailable'
    snapshot = AlertSignalSnapshot.query.one()
    assert snapshot.status == 'failed'
    assert snapshot.payload_json is None
    assert 'PRIVATE' not in str(snapshot.last_error)
    assert read_vault_alert_observations(binding_id=binding.id)['state'] == 'unavailable'


def test_foreign_alert_source_blocks_snapshot_no_secret_leak(store, monkeypatch):
    vault, _source_identity, _provider, binding = _source()
    wrong = _alert(vault.id)
    wrong['labels']['vault_instance'] = '999'
    monkeypatch.setattr(vault_jobs, 'build_client', lambda _provider: SimpleNamespace(
        get_alerts=lambda **_kwargs: [wrong],
    ))
    assert vault_jobs.observe_vault_alert_binding(binding.id, key=KEY) == 'blocked'
    snapshot = AlertSignalSnapshot.query.one()
    assert snapshot.status == 'failed'
    assert snapshot.payload_json is None
    assert 'PRIVATE' not in str(snapshot.last_error)


def test_missing_canonical_job_does_not_invoke_provider_or_worker_context(monkeypatch):
    monkeypatch.setattr(
        vault_jobs, 'JobExecutionContext',
        lambda *_a: pytest.fail('No job identity must not create a context'),
    )
    assert vault_jobs.run_vault_alert_observation_job(
        task_id='unregistered', job_execution_id=None, binding_ids=[44],
    )['status'] == 'blocked'


def test_no_automatic_or_alertcase_mutation_path_in_registered_job():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    content = (root / 'app/intelligence/alert_signals/vault_jobs.py').read_text(encoding='utf-8')
    assert 'AlertCase' not in content.replace('AlertCases', '')
    assert 'firing_routes(' not in content
    assert 'send_channel' not in content
    assert 'get_alerts(filters=' in content
    assert 'get_alerts(' in content
    assert 'get_job_definition' not in content


def _fake_canonical_job(*, payload=None, status='queued', actor=9):
    return SimpleNamespace(
        celery_task_id='task-id-1',
        job_type=vault_jobs.JOB_TYPE,
        operation=vault_jobs.OPERATION,
        scope_type='secrets_pki_alert_fleet',
        scope_key='all',
        integration_type='secrets_pki',
        status=status,
        requested_by_user_id=actor,
        payload_json={'trigger_type': 'manual'} if payload is None else payload,
    )


def _patch_job_boundary(monkeypatch, job):
    results = []

    class FakeContext:
        def __init__(self, task_id, job_id):
            assert task_id == 'task-id-1'
            assert job_id == 31

        def start(self, **kw):
            results.append(('start', kw))

        def checkpoint(self, **kw):
            results.append(('checkpoint', kw))

        def fail(self, message, **kw):
            results.append(('fail', message))

        def succeed(self, **kw):
            results.append(('succeed', kw))

        def canceled(self):
            results.append(('canceled', None))

    monkeypatch.setattr(vault_jobs, 'JobExecutionContext', FakeContext)
    monkeypatch.setattr(
        vault_jobs, 'db',
        SimpleNamespace(session=SimpleNamespace(
            get=lambda _cls, _id: job,
            rollback=lambda: None,
        )),
    )
    return results


def test_manual_job_worker_rejects_scheduler_actor_and_cancel_requested(monkeypatch):
    for job in (
        _fake_canonical_job(payload={'trigger_type': 'scheduled'}),
        _fake_canonical_job(status='cancel_requested'),
        _fake_canonical_job(actor=None),
    ):
        _patch_job_boundary(monkeypatch, job)
        monkeypatch.setattr(
            vault_jobs, 'build_vault_alert_observation_targets',
            lambda: pytest.fail('Unauthorized source must not be selected'),
        )
        output = vault_jobs.run_vault_alert_observation_job(
            task_id='task-id-1', job_execution_id=31, binding_ids=[41],
        )
        assert output['status'] == 'blocked'


def test_changed_target_is_terminal_failure_without_provider_call(monkeypatch):
    records = _patch_job_boundary(monkeypatch, _fake_canonical_job())
    monkeypatch.setattr(
        vault_jobs, 'build_vault_alert_observation_targets',
        lambda: (_ for _ in ()).throw(vault_jobs.NoEligibleVaultAlertSources('no valid scope')),
    )
    monkeypatch.setattr(
        vault_jobs, 'observe_vault_alert_binding',
        lambda *_a, **_kw: pytest.fail('Invalid target must not query provider'),
    )
    output = vault_jobs.run_vault_alert_observation_job(
        task_id='task-id-1', job_execution_id=31, binding_ids=[41],
    )
    assert output['status'] == 'failed'
    assert records == [('fail', 'Vault Alert Source target admission changed.')]


def test_missing_worker_key_fails_job_without_polling(monkeypatch):
    records = _patch_job_boundary(monkeypatch, _fake_canonical_job())
    monkeypatch.setattr(vault_jobs, 'build_vault_alert_observation_targets', lambda: [41])
    monkeypatch.setattr(vault_jobs, '_worker_key', lambda: None)
    monkeypatch.setattr(
        vault_jobs, 'observe_vault_alert_binding',
        lambda *_a, **_kw: pytest.fail('Missing worker key must not query provider'),
    )
    output = vault_jobs.run_vault_alert_observation_job(
        task_id='task-id-1', job_execution_id=31, binding_ids=[41],
    )
    assert output['status'] == 'failed'
    assert records == [('fail', 'Vault alert correlation secret is unavailable.')]


def test_admitted_job_returns_only_sanitized_counts(monkeypatch):
    records = _patch_job_boundary(monkeypatch, _fake_canonical_job())
    monkeypatch.setattr(vault_jobs, 'build_vault_alert_observation_targets', lambda: [41])
    monkeypatch.setattr(vault_jobs, '_worker_key', lambda: KEY)
    monkeypatch.setattr(vault_jobs, 'observe_vault_alert_binding', lambda _id, *, key: 'qualified')
    output = vault_jobs.run_vault_alert_observation_job(
        task_id='task-id-1', job_execution_id=31, binding_ids=[41],
    )
    assert output == {
        'status': 'success',
        'observed_sources': 1,
        'unobserved_sources': 0,
        'failed_sources': 0,
    }
    assert records[-1][0] == 'succeed'
    assert 'PRIVATE' not in repr(records)


def test_manual_only_config_is_in_jobs_registry_not_celery_beat():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    path = root / 'app/templates/platform_operations/jobs/configuration/definitions/vault_alert_observation.html'
    content = path.read_text(encoding='utf-8')
    assert '_job_overview.html' in content
    assert '_execution_activity.html' in content
    assert 'Automatic policy is unsupported' in content
    assert 'update_policy' not in content
    assert 'policy_form.enabled' not in content
