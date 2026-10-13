from __future__ import annotations

from app.artifact_registry.governance_tasks import _governance_sync_result
from app.integrations.registry.providers.harbor.exceptions import HarborError
from app.integrations.registry.providers.harbor.governance import (
    _project_governance_record,
    _replication_policies,
    _state,
)


def _states():
    return {
        name: _state(supported=True, observed=True) for name in ('retention', 'immutability', 'replication', 'webhook')
    }


class _ProjectDetailUnavailable:
    def get_project(self, *, project_name_or_id: str):
        raise HarborError('Project detail is inaccessible')

    def list_immutability_rules(self, *, project_name_or_id: str):
        return []

    def list_webhook_policies(self, *, project_name_or_id: str):
        return []


class _ReplicationUnavailable:
    def list_all_replication_policies(self):
        raise HarborError('Replication API unavailable')


def test_project_detail_failure_is_not_a_false_not_configured_retention():
    states = _states()
    record = _project_governance_record(_ProjectDetailUnavailable(), {'name': 'team'}, states)
    assert record is not None
    assert record.retention_status == 'unavailable'
    assert record.retention_summary['collection_state'] == 'project_detail_unavailable'
    assert states['retention']['status'] == 'unavailable'


def test_replication_api_failure_is_distinguishable_from_observed_empty():
    states = _states()
    assert _replication_policies(_ReplicationUnavailable(), states) == []
    assert states['replication']['status'] == 'unavailable'


def test_partially_collected_governance_is_warning_not_success():
    result = _governance_sync_result(
        total=1,
        synced=1,
        project_count=3,
        replication_policy_count=0,
        failures=[],
        partial_sources=1,
        requested_by_user_id=None,
        started=0,
    )
    assert result['status'] == 'warning'
    assert result['partial_count'] == 1
    assert 'retained' in result['detail']


def test_failed_sources_remain_failure_even_with_partial_counter():
    result = _governance_sync_result(
        total=1,
        synced=0,
        project_count=0,
        replication_policy_count=0,
        failures=[{'integration_instance_id': '1', 'message': 'failed'}],
        partial_sources=0,
        requested_by_user_id=None,
        started=0,
    )
    assert result['status'] == 'error'


def test_malformed_harbor_project_discovery_fails_instead_of_deleting_prior_evidence(monkeypatch):
    import pytest

    from app.integrations.registry.providers.harbor import governance as harbor

    class Client:
        def list_all_projects(self):
            return [{'project_id': 42}]

    monkeypatch.setattr(harbor, 'build_client', lambda _instance: Client())
    with pytest.raises(harbor.HarborResponseError, match='without a name'):
        harbor.collect_harbor_governance(object())


def test_malformed_replication_record_is_unavailable_not_observed_empty(monkeypatch):
    from app.integrations.registry.providers.harbor import governance as harbor

    class Client:
        def list_all_projects(self):
            return []

        def list_all_replication_policies(self):
            return [{'name': 'invalid-without-policy-id'}]

    monkeypatch.setattr(harbor, 'build_client', lambda _instance: Client())
    result = harbor.collect_harbor_governance(object())
    assert result.capability_states['replication']['status'] == 'unavailable'
