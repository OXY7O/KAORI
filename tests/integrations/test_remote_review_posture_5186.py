"""Historical remote receipt projection; no network or authorization."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.infrastructure_automation import remote_review_posture as service
from app.platform_operations.jobs.fingerprint import payload_fingerprint


@pytest.fixture
def evidence(monkeypatch):
    now = datetime.now(UTC)
    metadata = {
        'source_sha': service.SOURCE_CANDIDATE_SHA,
        'execution_environment_digest': 'sha256:' + 'a' * 64,
    }
    connection = SimpleNamespace(
        id=31, integration_type='configuration_automation', provider_key='ansible', enabled=True,
        metadata_json=metadata,
    )
    params = {
        'schema_version': 1, 'actor_id': 7, 'connection_id': 31,
        'profile_sha': service.SOURCE_CANDIDATE_SHA, 'remote_candidate_sha': service.REMOTE_CANDIDATE_SHA,
        'ee_digest': metadata['execution_environment_digest'], 'inventory_fingerprint': 'b' * 64,
        'host_registry_fingerprint': 'c' * 64, 'target_review_fingerprint': 'd' * 64,
        'execution_authorized': False,
    }
    summary = {
        **params, 'source_review_fingerprint': 'e' * 64, 'worker_review_fingerprint': 'f' * 64,
        'expires_at': (now + timedelta(minutes=1)).isoformat(), 'status': 'review_evidence_recorded',
        'runtime_attestation_verified': False, 'full_preflight_verified': False,
        'credential_material_accessed': False, 'ssh_executed': False, 'mutation_authorized': False,
    }
    job = SimpleNamespace(
        integration_instance_id=31, integration_type='configuration_automation', job_type='infrastructure_automation',
        operation=service.REVIEW_OPERATION, queue_name='automation', workload_class='validation',
        scope_type='ansible_source_connection', scope_key='31', resource_group='kubespray:remote-preflight-review:31',
        requested_by_user_id=7, max_attempts=1, attempt_count=1, status='succeeded', completed_at=now - timedelta(seconds=2),
        result_type=service.REVIEW_RESULT_TYPE, result_summary_json=summary,
        payload_json={**params, '_progress': {}}, parameter_fingerprint=payload_fingerprint(params),
    )
    monkeypatch.setattr(service, 'committed_source_state', lambda metadata: 'checked')
    return connection, job, now


def test_historical_only_without_sensitive_projection(evidence):
    connection, job, now = evidence
    result = service.review_remote_job_posture(connection, job, now=now).presentation()
    assert result['state'] == 'historical'
    assert result['execution_authorized'] is False
    assert set(result) == {'state', 'label', 'tone', 'description', 'execution_authorized'}
    assert job.parameter_fingerprint not in str(result)


@pytest.mark.parametrize('change,state', [
    ('no_record', 'not_recorded'), ('queued', 'pending'), ('failed', 'blocked'),
    ('wrong_scope', 'unqualified'), ('wrong_actor', 'unqualified'), ('wrong_result', 'unqualified'),
    ('attempt', 'unqualified'), ('payload_drift', 'unqualified'), ('receipt_drift', 'unqualified'),
    ('true_flag', 'unqualified'), ('extra_key', 'unqualified'), ('bad_digest', 'unqualified'),
    ('future_completion', 'unqualified'), ('naive_completion', 'unqualified'),
    ('invalid_expiry', 'unqualified'), ('expired', 'expired'), ('changed_ee', 'source_changed'),
    ('disabled', 'source_changed'),
])
def test_latest_receipt_fail_closed(evidence, change, state):
    connection, job, now = evidence
    if change == 'no_record':
        job = None
    elif change in ('queued', 'failed'):
        job.status = change
    elif change == 'wrong_scope':
        job.scope_key = '32'
    elif change == 'wrong_actor':
        job.requested_by_user_id = 8
    elif change == 'wrong_result':
        job.result_type = 'fixture'
    elif change == 'attempt':
        job.attempt_count = 2
    elif change == 'payload_drift':
        job.payload_json['actor_id'] = 8
    elif change == 'receipt_drift':
        job.result_summary_json['target_review_fingerprint'] = 'a' * 64
    elif change == 'true_flag':
        job.result_summary_json['ssh_executed'] = True
    elif change == 'extra_key':
        job.result_summary_json['unexpected'] = 'fixture'
    elif change == 'bad_digest':
        job.result_summary_json['worker_review_fingerprint'] = 'invalid'
    elif change == 'future_completion':
        job.completed_at = now + timedelta(seconds=1)
    elif change == 'naive_completion':
        job.completed_at = job.completed_at.replace(tzinfo=None)
    elif change == 'invalid_expiry':
        job.result_summary_json['expires_at'] = 'invalid'
    elif change == 'expired':
        job.result_summary_json['expires_at'] = (now - timedelta(seconds=1)).isoformat()
    elif change == 'changed_ee':
        connection.metadata_json['execution_environment_digest'] = 'sha256:' + '9' * 64
    elif change == 'disabled':
        connection.enabled = False
    result = service.review_remote_job_posture(connection, job, now=now)
    assert result.state == state
    assert result.execution_authorized is False


def test_projection_selects_only_latest_attempt(evidence, monkeypatch):
    connection, job, _ = evidence
    job.status = 'failed'
    calls = []

    class Query:
        def filter_by(self, **kwargs):
            calls.append(kwargs)
            return self

        def order_by(self, *args):
            calls.append('ordered')
            return self

        def first(self):
            calls.append('first')
            return job

    order = SimpleNamespace(desc=lambda: None)
    monkeypatch.setattr(service, 'JobExecution', SimpleNamespace(query=Query(), created_at=order, id=order))
    assert service.committed_remote_review_posture(connection).state == 'blocked'
    assert calls == [
        {'integration_type': 'configuration_automation', 'integration_instance_id': 31,
         'operation': service.REVIEW_OPERATION}, 'ordered', 'first',
    ]
