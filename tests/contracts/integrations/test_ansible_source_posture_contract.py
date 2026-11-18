"""#4842: source-evidence posture must never claim operational readiness."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import render_template
from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.infrastructure_automation.kubernetes import committed_preflight
from app.integrations.orchestration.configuration_automation.providers.ansible import service as ansible_service
from app.integrations.orchestration.configuration_automation.providers.ansible.preflight import (
    build_kubespray_preflight,
)
from app.integrations.orchestration.configuration_automation.providers.ansible.service import (
    source_validation_posture,
)
from app.integrations.source_control.source_control.providers.github.public_automation_source import (
    ANSIBLE_CORE_VERSION,
    ANSIBLE_RUNNER_VERSION,
    KUBESPRAY_RELEASE,
    PROFILE_KEY,
    REPOSITORY,
    SOURCE_CANDIDATE_SHA,
)

_PARTIAL = 'integrations/orchestration/configuration_automation/providers/ansible/_detail_validation.html'


def _connection(*, state: str = 'source_checked', **changes):
    meta = {
        'profile_key': PROFILE_KEY,
        'source_repository': REPOSITORY,
        'source_sha': SOURCE_CANDIDATE_SHA,
        'ansible_core_version': ANSIBLE_CORE_VERSION,
        'ansible_runner_version': ANSIBLE_RUNNER_VERSION,
        'kubespray_release': KUBESPRAY_RELEASE,
        'execution_enabled': False,
        'mutation_authorized': False,
        'source_validation': {
            'status': state,
            'repository': REPOSITORY,
            'revision': SOURCE_CANDIDATE_SHA,
            'profile_key': PROFILE_KEY,
            'checked_files': 5,
            'operation_authorized': False,
            'observed_at': '2026-11-15T00:00:00+00:00',
        },
    }
    meta.update(changes)
    return SimpleNamespace(id=12, environment='laboratory', metadata_json=meta)


@pytest.mark.parametrize(('state', 'expected'), [('source_checked', 'checked'), ('blocked', 'blocked')])
def test_provider_service_commits_revalidation_without_enabling_execution(monkeypatch, state, expected):
    connection = _connection()
    connection.integration_type = 'configuration_automation'
    connection.provider_key = 'ansible'
    connection.readiness_status = 'ready'
    connection.health_status = 'healthy'
    connection.metadata_json['execution_enabled'] = True
    connection.metadata_json['mutation_authorized'] = True
    connection.metadata_json['independent_evidence'] = 'retained'
    proof = dict(connection.metadata_json['source_validation'])
    if state == 'blocked':
        proof = {'status': 'blocked', 'operation_authorized': False, 'checked_files': 0}
    events: list[str] = []
    monkeypatch.setattr(
        ansible_service,
        'db',
        SimpleNamespace(
            session=SimpleNamespace(
                commit=lambda: events.append('commit'),
                rollback=lambda: events.append('rollback'),
            )
        ),
    )

    ansible_service.commit_source_revalidation(connection, evidence=proof)

    assert events == ['commit']
    assert connection.metadata_json['source_validation'] == proof
    assert connection.metadata_json['independent_evidence'] == 'retained'
    assert connection.metadata_json['execution_enabled'] is False
    assert connection.metadata_json['mutation_authorized'] is False
    assert connection.readiness_status == 'validation_required'
    assert connection.health_status is None
    assert source_validation_posture(connection)['source_state'] == expected


def test_provider_service_rolls_back_failed_revalidation_commit(monkeypatch):
    connection = _connection()
    connection.integration_type = 'configuration_automation'
    connection.provider_key = 'ansible'
    events: list[str] = []

    def failed_commit():
        events.append('commit')
        raise SQLAlchemyError('synthetic revalidation commit failure')

    monkeypatch.setattr(
        ansible_service,
        'db',
        SimpleNamespace(
            session=SimpleNamespace(
                commit=failed_commit,
                rollback=lambda: events.append('rollback'),
            )
        ),
    )

    with pytest.raises(SQLAlchemyError, match='synthetic revalidation commit failure'):
        ansible_service.commit_source_revalidation(
            connection, evidence={'status': 'blocked', 'operation_authorized': False, 'checked_files': 0}
        )
    assert events == ['commit', 'rollback']


def test_valid_source_only_is_checked_but_all_operations_blocked():
    result = source_validation_posture(_connection())
    assert result['source_state'] == 'checked'
    assert build_kubespray_preflight is committed_preflight.build_kubespray_preflight
    assert committed_preflight.build_kubespray_preflight(_connection()).gates[0].state == 'ready'
    assert result['source_label'] == 'Source Checked'
    assert result['source_tone'] == 'normal'
    assert result['checked_files'] == 5
    assert result['runtime_authorized'] is False
    assert result['mutation_authorized'] is False
    assert len(result['capabilities']) == 9
    assert {operation for operation, _ in result['capabilities']} == {
        'Discover',
        'Preflight',
        'Plan',
        'Provision',
        'Verify',
        'Scale',
        'Upgrade',
        'Node Maintenance',
        'Recovery',
    }


@pytest.mark.parametrize('state', ('blocked', 'rejected', 'failed'))
def test_failed_source_readback_is_blocked_not_checked(state):
    result = source_validation_posture(_connection(state=state))
    assert result['source_state'] == 'blocked'
    assert result['source_tone'] == 'critical'
    assert result['checked_files'] == 0
    assert result['observed_at'] is None
    assert result['runtime_authorized'] is False


@pytest.mark.parametrize(
    ('changes', 'expected'),
    [
        ({'source_validation': {}}, 'not_checked'),
        ({'source_validation': None}, 'not_checked'),
        ({'source_validation': 'source_checked'}, 'not_checked'),
        ({'source_sha': '0' * 40}, 'blocked'),
        ({'kubespray_release': 'latest'}, 'blocked'),
        ({'ansible_core_version': '2.20.0'}, 'blocked'),
        ({'source_validation': {'status': 'source_checked'}}, 'blocked'),
    ],
)
def test_missing_or_mismatched_metadata_never_claims_source_checked(changes, expected):
    connection = _connection(**changes)
    result = source_validation_posture(connection)
    assert committed_preflight.build_kubespray_preflight(connection).gates[0].state == 'blocked'
    assert result['source_state'] == expected
    assert result['source_tone'] == ('critical' if expected == 'blocked' else 'unknown')
    assert not result['source_checked']
    assert result['runtime_authorized'] is False


@pytest.mark.parametrize('state', ('source_checked', 'blocked', 'not_checked'))
def test_rendered_validation_status_tracks_committed_evidence(state):
    app = create_app('testing')
    connection = _connection(state=state)
    if state == 'not_checked':
        connection.metadata_json['source_validation'] = None
    status = source_validation_posture(connection)
    with app.test_request_context('/integrations/ansible/connections/12'):
        rendered = render_template(
            _PARTIAL,
            connection=connection,
            source=connection.metadata_json,
            evidence=connection.metadata_json.get('source_validation') or {},
            source_posture=status,
            kubespray_preflight=build_kubespray_preflight(connection).presentation(),
        )
    assert status['source_label'] in rendered
    assert 'Operation Eligibility' in rendered
    assert 'Kubespray Preflight &amp; Plan Readiness' in rendered
    assert 'Plan, Approval &amp; Change Window' in rendered
    assert rendered.count('Blocked') >= 9
    assert 'Revalidate Source' in rendered
    assert 'csrf_token' in rendered
    assert 'No approved' in rendered
    if state != 'source_checked':
        assert 'Verified files: 0' in rendered
        assert 'Source Checked' not in rendered
