from __future__ import annotations

from types import SimpleNamespace

from app.artifact_registry.eligibility import RegistryInventoryEligibility
from app.integrations.registry.providers.harbor import _record_failure, runtime, validation
from app.integrations.registry.providers.harbor.adapter import HarborRuntimeAdapter
from app.integrations.registry.providers.harbor.application import presentation
from app.integrations.registry.providers.harbor.exceptions import HarborAuthError


class _ReadyClient:
    def test_connection(self):
        return {
            'connected': True,
            'response_time_ms': 7,
            'version': 'v2.15.2',
            'registry_url': 'registry.example.test',
            'external_url': 'https://harbor.example.test',
        }

    def get_health(self):
        return {'status': 'unhealthy', 'components': [{'name': 'database', 'status': 'unhealthy'}]}

    def list_projects(self, *, page=1, page_size=1):
        return [{'name': 'library'}]

    def list_repositories(self, *, project_name_or_id, page=1, page_size=1):
        assert project_name_or_id == 'library'
        return []


class _MissingRepositoryClient(_ReadyClient):
    def get_health(self):
        return {'status': 'healthy', 'components': []}

    def list_repositories(self, *, project_name_or_id, page=1, page_size=1):
        raise HarborAuthError('Harbor authentication or authorization failed with HTTP 403.', status=403)


class _NoVisibleProjectClient(_ReadyClient):
    def list_projects(self, *, page=1, page_size=1):
        return []

    def list_repositories(self, *, project_name_or_id, page=1, page_size=1):
        raise AssertionError('Repository discovery must not run without a visible project.')


def _source():
    return SimpleNamespace(
        id=41,
        name='Harbor Test',
        provider_key='harbor',
        adapter_key='harbor_api_v2',
        endpoint='https://harbor.example.test',
        timeout=5,
        detected_version=None,
        compatibility_status=None,
        compatibility_profile=None,
        capability_profile=None,
        capabilities=None,
        validation_summary=None,
        readiness_status='validation_required',
        validation_message=None,
        last_validated_at=None,
        last_response_time_ms=None,
        last_status=None,
        last_error=None,
        last_checked_at=None,
    )


def _stub_persistence(monkeypatch, module):
    commits: list[bool] = []
    statuses: list[dict[str, object]] = []

    monkeypatch.setattr(module.db.session, 'commit', lambda: commits.append(True))

    def mark_status(instance, **kwargs):
        statuses.append(kwargs)
        instance.last_status = kwargs.get('status')
        instance.last_error = kwargs.get('error')
        instance.last_response_time_ms = kwargs.get('response_time_ms')

    monkeypatch.setattr(module, 'mark_status', mark_status)
    return commits, statuses


def test_test_connection_does_not_mutate_full_validation_readiness(monkeypatch) -> None:
    source = _source()
    client = _ReadyClient()
    monkeypatch.setattr(validation, 'build_client', lambda _source: client)

    result = validation.test_connection(source)

    assert result['connected'] is True
    assert result['version'] == 'v2.15.2'
    assert source.readiness_status == 'validation_required'
    assert source.compatibility_status is None
    assert source.capabilities is None
    assert source.last_validated_at is None


def test_full_validation_keeps_provider_health_signal_distinct_from_readiness(monkeypatch) -> None:
    source = _source()
    commits, statuses = _stub_persistence(monkeypatch, validation)
    monkeypatch.setattr(validation, 'build_client', lambda _source: _ReadyClient())

    result = validation.validate_source(source, source_label='Harbor Test')

    assert result.connected is True
    assert result.readiness_status == 'ready'
    assert result.compatibility_status == 'compatible'
    assert set(result.capabilities) == {
        'provider_health',
        'system_identity',
        'project_discovery',
        'repository_discovery',
    }
    assert source.readiness_status == 'ready'
    assert source.validation_summary['provider_health']['status'] == 'unhealthy'
    assert any(step.key == 'provider_health' and step.status == 'warning' for step in result.validation_steps)
    runtime_state = HarborRuntimeAdapter().get_state(source, validation_result=result)
    assert runtime_state.readiness == 'ready'
    assert runtime_state.health.status == 'degraded'
    assert commits == [True]
    assert statuses[-1]['status'] == 'connected'


def test_full_validation_blocks_when_required_repository_capability_is_missing(monkeypatch) -> None:
    source = _source()
    _stub_persistence(monkeypatch, validation)
    monkeypatch.setattr(validation, 'build_client', lambda _source: _MissingRepositoryClient())

    result = validation.validate_source(source, source_label='Harbor Test')

    assert result.connected is True
    assert result.readiness_status == 'blocked'
    assert result.compatibility_status == 'capability_mismatch'
    assert 'repository_discovery' not in result.capabilities
    assert source.readiness_status == 'blocked'
    assert 'repository_discovery' in (result.error or '')
    assert any(step.key == 'repository_discovery' and step.status == 'failed' for step in result.validation_steps)


def test_full_validation_blocks_when_no_project_can_anchor_repository_discovery(monkeypatch) -> None:
    source = _source()
    _stub_persistence(monkeypatch, validation)
    monkeypatch.setattr(validation, 'build_client', lambda _source: _NoVisibleProjectClient())

    result = validation.validate_source(source, source_label='Harbor Test')

    assert result.connected is True
    assert result.readiness_status == 'blocked'
    assert 'project_discovery' in result.capabilities
    assert 'repository_discovery' not in result.capabilities
    assert any(
        step.key == 'repository_discovery'
        and step.status == 'failed'
        and 'no visible project' in step.detail
        for step in result.validation_steps
    )


def test_runtime_refresh_updates_health_without_rebuilding_validation_authority(monkeypatch) -> None:
    source = _source()
    source.readiness_status = 'ready'
    source.compatibility_status = 'compatible'
    source.compatibility_profile = 'harbor-api-v2-core-v1'
    source.capability_profile = 'registry-provider-read-v1'
    source.capabilities = [
        'provider_health',
        'system_identity',
        'project_discovery',
        'repository_discovery',
    ]
    source.validation_summary = {'required_capabilities_observed': list(source.capabilities)}
    source.validation_message = 'Qualified Harbor release.'

    commits, statuses = _stub_persistence(monkeypatch, runtime)
    monkeypatch.setattr(runtime, 'build_client', lambda _source: _ReadyClient())

    result = runtime.refresh_instance_health(source)

    assert result['connected'] is True
    assert result['health_status'] == 'unhealthy'
    assert source.readiness_status == 'ready'
    assert source.compatibility_status == 'compatible'
    assert source.compatibility_profile == 'harbor-api-v2-core-v1'
    assert source.capability_profile == 'registry-provider-read-v1'
    assert source.capabilities == [
        'provider_health',
        'system_identity',
        'project_discovery',
        'repository_discovery',
    ]
    assert source.validation_summary['runtime_health']['status'] == 'unhealthy'
    assert source.validation_summary['required_capabilities_observed'] == source.capabilities
    assert commits == [True]
    assert statuses[-1]['status'] == 'connected'


def test_failure_recorder_persists_normalized_detail_without_raw_secret() -> None:
    source = _source()
    source.timeout = 5
    raw_secret = 'never-persist-this-secret'

    _record_failure(source, RuntimeError(f'provider exploded around {raw_secret}'))

    assert source.last_status == 'disconnected'
    assert raw_secret not in (source.last_error or '')
    assert 'KAORI could not complete the Harbor connection test' in (source.last_error or '')
    assert source.last_checked_at is not None
    assert source.last_response_time_ms is None


def test_inventory_status_surfaces_validation_prerequisite_before_first_snapshot() -> None:
    status = presentation._inventory_status(
        None,
        eligibility=RegistryInventoryEligibility(
            eligible=False,
            readiness='validation_required',
            compatibility_status='',
            reason='Run Full Validation before Artifact Registry inventory synchronization.',
        ),
    )

    assert status == {
        'status': 'attention',
        'label': 'Validation Required',
        'detail': 'Run Full Validation before Artifact Registry inventory synchronization.',
    }


def test_inventory_status_keeps_not_collected_after_validation_until_inventory_sync() -> None:
    status = presentation._inventory_status(
        None,
        eligibility=RegistryInventoryEligibility(
            eligible=True,
            readiness='ready',
            compatibility_status='compatible',
            reason='Registry provider is fully ready for inventory collection.',
        ),
    )

    assert status['status'] == 'unknown'
    assert status['label'] == 'Not Collected'
    assert 'Artifact Registry inventory synchronization' in status['detail']
