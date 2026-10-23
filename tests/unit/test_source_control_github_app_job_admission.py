"""SC-02 can use the existing durable JobExecution path only after admission."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.integrations.source_control.source_control.providers.github import job_admission
from app.integrations.source_control.source_control.providers.github.transport import GitHubProviderError


def _instance() -> SimpleNamespace:
    canonical = SimpleNamespace(
        id=14, integration_type='source_control', provider_key='github',
        adapter_key='github_rest_v3', enabled=True, lifecycle_status='active',
    )
    credential = SimpleNamespace(
        id=9, native_app_id='42', host_key='github.com', enabled=True,
    )
    return SimpleNamespace(
        id=3, integration_instance_id=14, integration_instance=canonical,
        provider_key='github', host_key='github.com', native_app_id='42',
        github_app_credential_id=9, github_app_credential=credential,
        account=SimpleNamespace(native_account_id='7'),
    )


def _admit(monkeypatch) -> None:
    monkeypatch.setattr(
        job_admission, 'provider_kind', lambda *_: SimpleNamespace(available=True)
    )
    implementation = SimpleNamespace(provider_key='github')
    module = SimpleNamespace(
        require_record_for_canonical=lambda _id: _instance(),
        implementation_for_record=lambda _instance: implementation,
    )
    monkeypatch.setattr(job_admission, 'get_integration', lambda _: module)


def test_planned_provider_does_not_create_job(monkeypatch) -> None:
    monkeypatch.setattr(
        job_admission, 'provider_kind', lambda *_: SimpleNamespace(available=False)
    )
    monkeypatch.setattr(
        job_admission, 'enqueue_instance_validation',
        lambda **_: pytest.fail('planned GitHub must not create a JobExecution'),
    )
    with pytest.raises(GitHubProviderError, match='admission is pending'):
        job_admission.enqueue_github_app_job(
            _instance(), operation='full_validation', requested_by_user_id=1
        )


def test_unregistered_kernel_blocks_job_before_celery(monkeypatch) -> None:
    _admit(monkeypatch)
    monkeypatch.setattr(
        job_admission, 'get_integration',
        lambda _: (_ for _ in ()).throw(RuntimeError('Kernel not admitted')),
    )
    monkeypatch.setattr(
        job_admission, 'enqueue_instance_validation',
        lambda **_: pytest.fail('unregistered module must not create a job'),
    )
    with pytest.raises(RuntimeError, match='Kernel not admitted'):
        job_admission.enqueue_github_app_job(
            _instance(), operation='full_validation', requested_by_user_id=1
        )


@pytest.mark.parametrize('attribute,value', [
    ('provider_key', 'not-github'),
    ('host_key', 'ghes.internal'),
    ('github_app_credential_id', 123),
    ('account', None),
])
def test_cross_scope_identity_blocks_job(monkeypatch, attribute, value) -> None:
    _admit(monkeypatch)
    installation = _instance()
    setattr(installation, attribute, value)
    monkeypatch.setattr(
        job_admission, 'enqueue_runtime_health_refresh',
        lambda **_: pytest.fail('mismatched installation must not schedule a job'),
    )
    with pytest.raises(GitHubProviderError, match='not eligible'):
        job_admission.enqueue_github_app_job(
            installation, operation='runtime_refresh', requested_by_user_id=1
        )


def test_full_validation_uses_only_canonical_identity_and_actor(monkeypatch) -> None:
    _admit(monkeypatch)
    calls = []
    monkeypatch.setattr(
        job_admission, 'enqueue_instance_validation',
        lambda **kwargs: (calls.append(kwargs) or ({'job_execution_id': 123}, True)),
    )
    payload, created = job_admission.enqueue_github_app_job(
        _instance(), operation='full_validation', requested_by_user_id=91
    )
    assert created
    assert payload['job_execution_id'] == 123
    assert calls == [{
        'integration_type': 'source_control',
        'integration_instance_id': 14,
        'requested_by_user_id': 91,
    }]
    assert 'secret' not in repr(calls).lower()
    assert 'token' not in repr(calls).lower()


def test_runtime_refresh_reuses_canonical_worker_and_dedup(monkeypatch) -> None:
    _admit(monkeypatch)
    calls = []
    monkeypatch.setattr(
        job_admission, 'enqueue_runtime_health_refresh',
        lambda **kwargs: (calls.append(kwargs) or ({'job_execution_id': 123}, False)),
    )
    payload, created = job_admission.enqueue_github_app_job(
        _instance(), operation='runtime_refresh', requested_by_user_id=91
    )
    assert payload['job_execution_id'] == 123
    assert created is False
    assert calls[0]['integration_type'] == 'source_control'


@pytest.mark.parametrize('actor', [0, -1, True])
def test_job_requires_authenticated_actor(actor) -> None:
    with pytest.raises(ValueError, match='authenticated'):
        job_admission.enqueue_github_app_job(
            _instance(), operation='full_validation', requested_by_user_id=actor
        )


def test_unrecognized_job_operation_does_not_schedule() -> None:
    with pytest.raises(ValueError, match='Unsupported'):
        job_admission.enqueue_github_app_job(
            _instance(), operation='binding_validation', requested_by_user_id=91
        )
