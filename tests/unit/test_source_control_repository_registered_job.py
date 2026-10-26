"""SC-03 canonical job admission, disabled-by-default policy and safe queue contract."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.integrations.source_control import job_adapter, sync_jobs


def _installation():
    identity = SimpleNamespace(
        id=7,
        integration_type='source_control',
        provider_key='github',
        adapter_key='github_rest_v3',
        enabled=True,
        lifecycle_status='active',
        readiness_status='ready',
    )
    account = SimpleNamespace(id=6, provider_key='github', host_key='github.com')
    app = SimpleNamespace(id=5, enabled=True, host_key='github.com', native_app_id='42')
    return SimpleNamespace(
        id=8,
        integration_instance=identity,
        integration_instance_id=7,
        provider_key='github',
        host_key='github.com',
        native_app_id='42',
        repository_scope='selected',
        account=account,
        account_id=6,
        github_app_credential=app,
        github_app_credential_id=5,
    )


def test_planned_provider_blocks_sync_before_database(monkeypatch):
    monkeypatch.setattr(
        sync_jobs,
        'provider_kind',
        lambda *_: SimpleNamespace(available=False),
    )
    with pytest.raises(sync_jobs.NoEligibleSourceControlTargets, match='pending'):
        sync_jobs.build_source_repository_targets()


def test_validated_provider_identity_still_requires_approved_credentials():
    instance = _installation()
    assert sync_jobs._eligible(instance)
    instance.github_app_credential.enabled = False
    assert not sync_jobs._eligible(instance)
    instance.github_app_credential.enabled = True
    instance.native_app_id = 'different-app'
    assert not sync_jobs._eligible(instance)


def test_partial_validation_cannot_become_inventory_eligible():
    instance = _installation()
    instance.integration_instance.readiness_status = 'validation_required'
    assert not sync_jobs._eligible(instance)


def test_job_dispatcher_gates_before_canonical_job_creation(monkeypatch):
    monkeypatch.setattr(
        sync_jobs,
        'provider_kind',
        lambda *_: SimpleNamespace(available=False),
    )
    monkeypatch.setattr(
        sync_jobs,
        'enqueue_canonical_job',
        lambda **_kwargs: pytest.fail('planned provider may not enqueue job'),
    )
    result = job_adapter.dispatch_source_repositories(
        requested_by_user_id=9,
        trigger_type='scheduled',
    )
    assert result.status == 'blocked'
    assert not result.accepted


def test_canonical_job_sends_only_bound_ids_and_requires_worker(monkeypatch):
    instance = _installation()
    calls = []
    monkeypatch.setattr(
        sync_jobs,
        'build_source_repository_targets',
        lambda **_: [{'installation_id': instance.id}],
    )
    monkeypatch.setattr(
        sync_jobs,
        'enqueue_canonical_job',
        lambda **kwargs: calls.append(kwargs) or (object(), True),
    )
    job, created = sync_jobs.enqueue_source_repository_sync(
        requested_by_user_id=None,
        trigger_type='scheduled',
    )
    assert created and job is not None
    args = calls[0]
    assert args['job_type'] == 'source_control_repository_inventory'
    assert args['queue_name'] == 'inventory'
    assert args['dispatch_options'].require_registered_worker is True
    assert args['task_kwargs']['targets'] == [{'installation_id': 8}]
    assert args['max_attempts'] == 1
    assert 'token' not in repr(args['task_kwargs']).lower()
    assert 'pem' not in repr(args['task_kwargs']).lower()


@pytest.mark.parametrize('scope', [0, '-1', True, '1?admin=1'])
def test_dispatcher_never_broadens_bad_installation_scope(scope):
    result = job_adapter.dispatch_source_repositories(
        requested_by_user_id=1,
        trigger_type='manual',
        parameters={'installation_record_id': scope},
    )
    assert result.status == 'blocked'
    assert not result.accepted


def test_registered_job_starts_disabled_without_new_queue():
    from app.platform_operations.jobs.registry import get_job_definition

    definition = get_job_definition('source_control.repository.sync')
    assert definition.default_enabled is False
    assert definition.manual_execution_supported is False
    assert definition.queue_name == 'inventory'
    assert definition.domain_execute_permission == 'integrations.manage'
    assert definition.operation == 'sync_source_control_repositories'
    assert definition.configuration_template.endswith('source_control_repository_sync.html')


def test_manual_job_execution_is_blocked_until_724_scoped_policy():
    result = job_adapter.dispatch_source_repositories(
        requested_by_user_id=11,
        trigger_type='manual',
    )
    assert result.status == 'blocked'
    assert not result.accepted


def test_on_demand_refresh_rejects_actor_scope_bypass():
    with pytest.raises(sync_jobs.NoEligibleSourceControlTargets, match='end-user'):
        sync_jobs.enqueue_source_repository_sync(
            requested_by_user_id=10,
            trigger_type='on_demand',
            installation_record_id=8,
        )
