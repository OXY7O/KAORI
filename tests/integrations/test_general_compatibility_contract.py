from app.integrations.compatibility import (
    CONTRACT_PROFILES,
    QUALIFICATIONS,
    evaluate_compatibility,
    kubernetes_lifecycle,
    kubernetes_lifecycle_policy,
)


def test_general_contract_profiles_are_separate_from_version_qualifications() -> None:
    assert {
        'kubernetes-core-v1',
        'prometheus-http-core-v1',
        'alertmanager-api-v2-contract-v1',
    }.issubset(CONTRACT_PROFILES)

    alertmanager = QUALIFICATIONS['alertmanager']
    assert {item.contract_profile for item in alertmanager} == {'alertmanager-api-v2-contract-v1'}

    thanos = QUALIFICATIONS['thanos']
    assert {item.contract_profile for item in thanos} == {'prometheus-http-core-v1'}
    assert len(thanos) <= 2


def test_alertmanager_034_is_qualified_by_general_api_v2_contract() -> None:
    result = evaluate_compatibility(
        'alertmanager',
        '0.34.1',
        capabilities={'status_v2', 'alerts_v2', 'silences_v2'},
    )

    assert result.status == 'compatible'
    assert result.readiness == 'ready'
    assert result.profile_key == 'alertmanager-api-v2-contract-v1'
    assert result.qualification_key == 'alertmanager-current'
    assert result.upstream_lifecycle == 'current'


def test_future_alertmanager_version_with_required_api_is_unverified_not_blocked() -> None:
    result = evaluate_compatibility(
        'alertmanager',
        '0.35.0',
        capabilities={'status_v2', 'alerts_v2', 'silences_v2'},
    )

    assert result.status == 'unverified_version'
    assert result.readiness == 'degraded'
    assert result.profile_key == 'alertmanager-api-v2-contract-v1'
    assert result.qualification_key is None
    assert result.support_level == 'unverified'


def test_future_alertmanager_version_still_blocks_when_required_api_is_missing() -> None:
    result = evaluate_compatibility(
        'alertmanager',
        '0.35.0',
        capabilities={'status_v2'},
    )

    assert result.status == 'capability_mismatch'
    assert result.readiness == 'blocked'
    assert result.profile_key == 'alertmanager-api-v2-contract-v1'
    assert result.missing_capabilities == ('alerts_v2', 'silences_v2')


def test_kubernetes_137_is_current_and_future_minor_is_unverified() -> None:
    assert kubernetes_lifecycle('1.37.0') == 'current'
    assert kubernetes_lifecycle('1.38.0') == 'unknown'

    policy = kubernetes_lifecycle_policy('1.37.0')
    assert policy['current_version_band'] == 'v1.35–v1.37'
    assert policy['upstream_supported_version_band'] == 'v1.35–v1.37'


def test_thanos_042_uses_shared_prometheus_http_contract() -> None:
    result = evaluate_compatibility(
        'thanos',
        '0.42.4',
        capabilities={'prometheus_api_v1', 'instant_query', 'range_query'},
    )

    assert result.readiness == 'ready'
    assert result.profile_key == 'prometheus-http-core-v1'
    assert result.qualification_key == 'thanos-current'
