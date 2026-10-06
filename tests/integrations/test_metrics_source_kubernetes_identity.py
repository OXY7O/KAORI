from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.integrations.observability.metrics_source.binding_profiles import BindingProbe, BindingValidationProfile
from app.integrations.observability.metrics_source.binding_validators import kubernetes as kubernetes_validator
from app.integrations.observability.metrics_source.binding_validators.kubernetes import validate_kubernetes_binding
from app.integrations.observability.metrics_source.query_profiles.feature_contracts import _filesystem_identity_keys
from app.models.integration import IntegrationBinding


def _binding(*, label: str = 'cluster', value: str = 'k8s-production') -> IntegrationBinding:
    binding = IntegrationBinding()
    binding.selector_json = {'matchers': [{'label': label, 'operator': '=', 'value': value}]}
    return binding


def _profile() -> BindingValidationProfile:
    return BindingValidationProfile(
        adapter_key='prometheus_http',
        asset_type='kubernetes_cluster',
        profile_key='kubernetes-metrics-v1',
        label='Kubernetes Metrics v1',
        probes=(),
        no_match_message='No scoped Kubernetes identity matched.',
        validation_strategy='custom',
    )


class _LabelClient:
    def __init__(self, values: list[str], *, provider_key: str = 'prometheus') -> None:
        self.values = values
        self.config = SimpleNamespace(provider_key=provider_key)

    def label_values(self, label: str) -> dict[str, Any]:
        assert label == 'cluster'
        return {'status': 'success', 'data': self.values}


def test_kubernetes_binding_requires_canonical_cluster_selector() -> None:
    result = validate_kubernetes_binding(
        client=_LabelClient(['k8s-production']), binding=_binding(label='job'), profile=_profile()
    )

    assert result.status == 'degraded'
    assert result.evidence['source_identity']['status'] == 'failed'
    assert result.evidence['source_identity']['expected'] == 'cluster=<stable-cluster-name>'


def test_kubernetes_binding_reports_missing_cluster_query_label_for_direct_prometheus() -> None:
    result = validate_kubernetes_binding(client=_LabelClient([]), binding=_binding(), profile=_profile())

    identity = result.evidence['source_identity']
    assert result.status == 'degraded'
    assert identity['status'] == 'failed'
    assert 'query-visible target label' in identity['recommendation']


def test_kubernetes_binding_reports_missing_thanos_source_identity() -> None:
    result = validate_kubernetes_binding(
        client=_LabelClient([], provider_key='thanos'),
        binding=_binding(),
        profile=_profile(),
    )

    identity = result.evidence['source_identity']
    assert result.status == 'degraded'
    assert identity['status'] == 'failed'
    assert 'external label on every source Prometheus' in identity['recommendation']


def test_kubernetes_binding_accepts_matching_cluster_identity(monkeypatch) -> None:
    class Client(_LabelClient):
        def query(self, expression: str) -> dict[str, Any]:
            return {'status': 'success', 'data': {'result': [{'value': [0, '1']}]}}

    profile = BindingValidationProfile(
        adapter_key='prometheus_http',
        asset_type='kubernetes_cluster',
        profile_key='kubernetes-metrics-v1',
        label='Kubernetes Metrics v1',
        probes=(
            BindingProbe(
                expression='count(kube_node_info)',
                signal_key='kube_node_info',
                label='Kubernetes node identity',
            ),
        ),
        no_match_message='No scoped Kubernetes identity matched.',
    )
    monkeypatch.setattr(
        kubernetes_validator.PromQLProfileAuditor,
        'audit',
        lambda _self, execute_queries=True: {
            'available_capabilities': ['kubernetes_identity'],
            'feature_contract_summary': {'status': 'ready'},
            'capability_assessments': [],
            'module_readiness': {},
            'retention': {},
            'profile': 'promql-kubernetes-v1',
            'checked_at': '2026-08-18T00:00:00+00:00',
        },
    )

    result = validate_kubernetes_binding(client=Client(['k8s-production']), binding=_binding(), profile=profile)

    assert result.status == 'ready'
    assert result.evidence['source_identity']['status'] == 'ready'
    assert result.matched_signal == 'kube_node_info'


def test_filesystem_identity_accepts_only_canonical_node_label() -> None:
    legacy_alias_rows = [{'metric': {'nodename': 'worker-1', 'mountpoint': '/var'}, 'value': [0, '1']}]
    canonical_rows = [{'metric': {'node': 'worker-1', 'mountpoint': '/var'}, 'value': [0, '1']}]

    assert _filesystem_identity_keys(legacy_alias_rows) == ()
    assert _filesystem_identity_keys(canonical_rows) == ('worker-1::/var',)
