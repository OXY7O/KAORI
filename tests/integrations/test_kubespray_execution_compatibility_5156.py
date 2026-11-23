"""#5156: five-year Kubernetes API compatibility is not Kubespray Run authority."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.infrastructure_automation.kubernetes.execution_compatibility import (
    assess_kubespray_execution_compatibility,
)
from app.infrastructure_automation.kubernetes.kubespray_preflight import KUBESPRAY_RELEASE
from app.infrastructure_automation.kubernetes.source_policy import (
    ANSIBLE_CORE_VERSION,
    ANSIBLE_RUNNER_VERSION,
    PROFILE_KEY,
    REPOSITORY,
    SOURCE_CANDIDATE_SHA,
)


def _connection(*, source_checked=True, digest='sha256:' + 'a' * 64):
    return SimpleNamespace(
        integration_type='configuration_automation',
        provider_key='ansible',
        metadata_json={
            'profile_key': PROFILE_KEY,
            'source_repository': REPOSITORY,
            'source_sha': SOURCE_CANDIDATE_SHA,
            'ansible_core_version': ANSIBLE_CORE_VERSION,
            'ansible_runner_version': ANSIBLE_RUNNER_VERSION,
            'kubespray_release': KUBESPRAY_RELEASE,
            'execution_environment_digest': digest,
            'source_validation': {
                'status': 'source_checked' if source_checked else 'blocked',
                'repository': REPOSITORY,
                'revision': SOURCE_CANDIDATE_SHA,
                'profile_key': PROFILE_KEY,
                'checked_files': 5,
                'operation_authorized': False,
            },
        },
    )


def _preflight(*, state='ready_for_review'):
    gates = [SimpleNamespace(state='ready') for _ in range(8)]
    gates.extend([SimpleNamespace(state='blocked') for _ in range(2)])
    return SimpleNamespace(state=state, facts_job_public_id='trusted-job' if state == 'ready_for_review' else None, gates=gates)


def test_review_only_qualification_never_grants_kubernetes_mutation():
    result = assess_kubespray_execution_compatibility(_connection(), _preflight())
    plan, *mutations = result.operations
    assert result.policy_key == 'kaori-compatibility-policy-v1'
    assert result.policy_window == '2021–2026'
    assert result.target_minor == '1.36'
    assert result.api_support_posture == 'current'
    assert plan.operation == 'plan_review'
    assert plan.state == 'qualified_for_review'
    assert all(item.state == 'blocked' and not item.execution_authorized for item in mutations)
    assert result.execution_authorized is False
    assert result.presentation()['execution_authorized'] is False


@pytest.mark.parametrize(
    ('target_minor', 'expected_api_state'),
    [
        ('1.23', 'extended'),
        ('1.34', 'extended'),
        ('1.37', 'current'),
        ('1.38', 'unknown'),
        ('1.22', 'end_of_life'),
        ('not-a-version', 'unknown'),
        ('', 'unknown'),
    ],
)
def test_kaori_api_support_is_not_an_execution_qualification(target_minor, expected_api_state):
    result = assess_kubespray_execution_compatibility(_connection(), _preflight(), target_minor=target_minor)
    assert result.api_support_posture == expected_api_state
    assert all(operation.state == 'blocked' for operation in result.operations)
    assert not result.execution_authorized


@pytest.mark.parametrize(
    'connection, preflight',
    [
        (_connection(source_checked=False), _preflight()),
        (_connection(digest=None), _preflight()),
        (_connection(digest='sha256:unverified'), _preflight()),
        (_connection(), _preflight(state='blocked')),
    ],
)
def test_missing_source_digest_or_trusted_host_preflight_blocks_plan(connection, preflight):
    result = assess_kubespray_execution_compatibility(connection, preflight)
    assert result.operations[0].state == 'blocked'
    assert result.operations[0].reason
    assert all(not item.execution_authorized for item in result.operations)


def test_wrong_provider_or_toolchain_pin_is_never_review_ready():
    conn = _connection()
    conn.provider_key = 'other'
    assert assess_kubespray_execution_compatibility(conn, _preflight()).operations[0].state == 'blocked'
    conn = _connection()
    conn.metadata_json['ansible_core_version'] = '2.20.0'
    assert assess_kubespray_execution_compatibility(conn, _preflight()).operations[0].state == 'blocked'


def test_worker_self_declared_approval_cannot_change_qualification():
    preflight = _preflight()
    preflight.worker_execution_admitted = True
    preflight.maker_checker_approval_verified = True
    result = assess_kubespray_execution_compatibility(_connection(), preflight)
    assert result.operations[0].state == 'qualified_for_review'
    assert all(item.state == 'blocked' for item in result.operations[1:])
    assert not result.execution_authorized

def test_rendered_ansible_validation_explains_distinct_compatibility_boundary():
    from flask import render_template

    from app import create_app
    from app.infrastructure_automation.kubernetes.committed_preflight import build_kubespray_preflight
    from app.integrations.orchestration.configuration_automation.providers.ansible.service import (
        source_validation_posture,
    )

    conn = _connection()
    conn.id = 12
    conn.environment = 'laboratory'
    conn.enabled = False
    preflight = build_kubespray_preflight(conn)
    policy = assess_kubespray_execution_compatibility(conn, preflight)
    app = create_app('testing')
    with app.test_request_context('/integrations/ansible/connections/12'):
        html = render_template(
            'integrations/orchestration/configuration_automation/providers/ansible/_detail_validation.html',
            connection=conn,
            source_posture=source_validation_posture(conn),
            kubespray_preflight=preflight.presentation(),
            kubespray_execution_compatibility=policy.presentation(),
        )
    assert 'Lifecycle Execution Compatibility' in html
    assert '2021–2026' in html
    assert 'Review-Only Plan' in html
    assert 'Execution Blocked' in html
    assert 'No operation can be queued yet.' in html
    assert 'Operation Eligibility' in html
