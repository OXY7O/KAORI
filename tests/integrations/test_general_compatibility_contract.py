from app.integrations.compatibility import (
    COMPATIBILITY_LIFECYCLE_POLICY,
    CONTRACT_PROFILES,
    PRODUCT_POLICIES,
    QUALIFICATIONS,
    compatibility_selection_policy,
    evaluate_compatibility,
    kubernetes_lifecycle,
    kubernetes_lifecycle_policy,
    resolve_contract_profile,
    resolve_qualification,
)


def test_general_contract_profiles_are_separate_from_annual_policy_and_version_qualifications() -> None:
    assert COMPATIBILITY_LIFECYCLE_POLICY.key == 'kaori-compatibility-policy-v1'
    assert COMPATIBILITY_LIFECYCLE_POLICY.version == 1
    assert COMPATIBILITY_LIFECYCLE_POLICY.policy_year == 2026
    assert COMPATIBILITY_LIFECYCLE_POLICY.lookback_years == 5
    assert COMPATIBILITY_LIFECYCLE_POLICY.anchor_year == 2021
    assert COMPATIBILITY_LIFECYCLE_POLICY.window_label == '2021–2026'

    assert {
        'kubernetes-core-v1',
        'prometheus-http-core-v1',
        'alertmanager-api-v2-contract-v1',
    }.issubset(CONTRACT_PROFILES)

    assert all(policy.selection_mode == 'automatic_detected_version' for policy in PRODUCT_POLICIES.values())

    alertmanager = QUALIFICATIONS['alertmanager']
    assert {item.contract_profile for item in alertmanager} == {'alertmanager-api-v2-contract-v1'}

    thanos = QUALIFICATIONS['thanos']
    assert {item.contract_profile for item in thanos} == {'prometheus-http-core-v1'}
    assert len(thanos) == 2


def test_runtime_version_automatically_selects_definition_band_and_contract() -> None:
    extended = resolve_qualification('alertmanager', '0.23.0')
    current = resolve_qualification('alertmanager', '0.34.1')
    future = resolve_qualification('alertmanager', '0.35.0')

    assert extended is not None
    assert extended.key == 'alertmanager-extended'
    assert extended.contract_profile == 'alertmanager-api-v2-contract-v1'
    assert current is not None
    assert current.key == 'alertmanager-current'
    assert current.contract_profile == 'alertmanager-api-v2-contract-v1'
    assert future is None

    resolved = resolve_contract_profile('alertmanager', '0.34.1')
    assert resolved is not None
    assert resolved.key == current.contract_profile

    selection = compatibility_selection_policy('alertmanager')
    assert selection['selection_mode'] == 'automatic_detected_version'
    assert selection['version_source'] == 'alertmanager_status_v2'
    assert selection['default_contract_profile'] == 'alertmanager-api-v2-contract-v1'


def test_alertmanager_034_is_current_under_policy_v1() -> None:
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


def test_alertmanager_anchor_window_release_is_extended_not_eol() -> None:
    result = evaluate_compatibility(
        'alertmanager',
        '0.23.0',
        capabilities={'status_v2', 'alerts_v2', 'silences_v2'},
    )

    assert result.status == 'compatible_with_warnings'
    assert result.readiness == 'degraded'
    assert result.support_level == 'extended_supported'
    assert result.qualification_key == 'alertmanager-extended'


def test_alertmanager_pre_window_release_is_end_of_life() -> None:
    result = evaluate_compatibility(
        'alertmanager',
        '0.22.0',
        capabilities={'status_v2', 'alerts_v2', 'silences_v2'},
    )

    assert result.status == 'end_of_life'
    assert result.readiness == 'blocked'
    assert result.support_level == 'end_of_life'
    assert result.upstream_lifecycle == 'kaori_end_of_life'


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


def test_kubernetes_lifecycle_is_derived_from_generic_definition_bands() -> None:
    assert kubernetes_lifecycle('1.22.17') == 'end_of_life'
    assert kubernetes_lifecycle('1.23.0') == 'extended'
    assert kubernetes_lifecycle('1.34.6') == 'extended'
    assert kubernetes_lifecycle('1.35.0') == 'current'
    assert kubernetes_lifecycle('1.37.1') == 'current'
    assert kubernetes_lifecycle('1.38.0') == 'unknown'

    policy = kubernetes_lifecycle_policy('1.37.1')
    assert policy['policy_version'] == 'v1'
    assert policy['policy_year'] == '2026'
    assert policy['anchor_year'] == '2021'
    assert policy['lookback_years'] == '5'
    assert policy['window_label'] == '2021–2026'
    assert policy['current_version_band'] == 'v1.35–v1.37'
    assert policy['upstream_supported_version_band'] == 'v1.35–v1.37'
    assert policy['supported_version_band'].startswith('v1.23–v1.37')
    assert policy['selection_mode'] == 'automatic_detected_version'
    assert policy['version_source'] == 'kubernetes_server_version'


def test_thanos_042_uses_shared_prometheus_http_contract() -> None:
    result = evaluate_compatibility(
        'thanos',
        '0.42.4',
        capabilities={'prometheus_api_v1', 'instant_query', 'range_query'},
    )

    assert result.readiness == 'ready'
    assert result.profile_key == 'prometheus-http-core-v1'
    assert result.qualification_key == 'thanos-current'


def test_thanos_band_capability_delta_is_applied_from_definition() -> None:
    result = evaluate_compatibility(
        'thanos',
        '0.42.4',
        capabilities={'instant_query', 'range_query'},
    )

    assert result.status == 'capability_mismatch'
    assert result.readiness == 'blocked'
    assert result.missing_capabilities == ('prometheus_api_v1',)


def test_thanos_024_is_extended_and_023_is_eol() -> None:
    extended = evaluate_compatibility(
        'thanos',
        '0.24.0',
        capabilities={'prometheus_api_v1', 'instant_query', 'range_query'},
    )
    eol = evaluate_compatibility(
        'thanos',
        '0.23.0',
        capabilities={'prometheus_api_v1', 'instant_query', 'range_query'},
    )

    assert extended.readiness == 'degraded'
    assert extended.support_level == 'extended_supported'
    assert eol.status == 'end_of_life'
    assert eol.readiness == 'blocked'
