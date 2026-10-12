"""SSAR failure never becomes positive Kubernetes capability evidence."""

from types import SimpleNamespace

import pytest
from kubernetes.client.rest import ApiException

from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api import (
    compatibility,
)


@pytest.mark.parametrize('status', [403, 404])
def test_self_subject_access_review_unavailable_is_not_authorization(monkeypatch, status):
    class DeniedReview:
        def __init__(self, _api):
            pass

        def create_self_subject_access_review(self, _review):
            raise ApiException(status=status, reason='SSAR not available')

    monkeypatch.setattr(compatibility, 'AuthorizationV1Api', DeniedReview)
    discovery = compatibility.KubernetesDiscovery(SimpleNamespace())
    assert discovery._can_i(compatibility.ApiCandidate('', 'v1', 'pods'), 'list') is False


@pytest.mark.parametrize(('allowed', 'expected'), [(True, True), (False, False)])
def test_self_subject_access_review_returns_observed_authorization(
    monkeypatch, allowed, expected
):
    class Review:
        def __init__(self, _api):
            pass

        def create_self_subject_access_review(self, _review):
            return SimpleNamespace(status=SimpleNamespace(allowed=allowed))

    monkeypatch.setattr(compatibility, 'AuthorizationV1Api', Review)
    discovery = compatibility.KubernetesDiscovery(SimpleNamespace())
    assert discovery._can_i(compatibility.ApiCandidate('', 'v1', 'namespaces'), 'list') is expected


def test_self_subject_access_review_transport_errors_remain_failures(monkeypatch):
    class FailingReview:
        def __init__(self, _api):
            pass

        def create_self_subject_access_review(self, _review):
            raise ApiException(status=500, reason='Error')

    monkeypatch.setattr(compatibility, 'AuthorizationV1Api', FailingReview)
    discovery = compatibility.KubernetesDiscovery(SimpleNamespace())
    with pytest.raises(ApiException):
        discovery._can_i(compatibility.ApiCandidate('', 'v1', 'pods'), 'get')


def test_required_feature_is_not_ready_when_rbac_proof_is_missing(monkeypatch):
    discovery = compatibility.KubernetesDiscovery(SimpleNamespace())
    monkeypatch.setattr(discovery, '_resources', lambda _candidate: {'pods': {'get', 'list'}})
    monkeypatch.setattr(discovery, '_can_i', lambda _candidate, _verb: False)
    result = discovery._evaluate_contract(
        compatibility.FeatureContract('inventory.pods', (compatibility.ApiCandidate('', 'v1', 'pods'),))
    )
    assert result['status'] == 'blocked'
    assert result['selected_api'] is None
    assert result['observed'][0]['denied_verbs'] == ['get', 'list']
