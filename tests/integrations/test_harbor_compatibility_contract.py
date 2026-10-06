from app.definitions.integration_registry import integration_provider_document
from app.integrations.compatibility import (
    compatibility_selection_policy,
    evaluate_compatibility,
    PRODUCT_POLICIES,
    resolve_contract_profile,
    resolve_qualification,
)
CORE_CAPABILITIES = {
    'provider_health',
    'system_identity',
    'project_discovery',
    'repository_discovery',
}


def test_harbor_policy_v1_uses_definition_driven_five_year_window() -> None:
    policy = PRODUCT_POLICIES['harbor']

    assert policy.contract_profile == 'harbor-api-v2-core-v1'
    assert policy.qualification_floor == '2.4.1'
    assert policy.qualification_ceiling_exclusive == '2.16'
    assert policy.current_version_label == 'v2.13–v2.15'
    assert policy.recommended_label == 'v2.15.2'

    selection = compatibility_selection_policy('harbor')
    assert selection == {
        'selection_mode': 'automatic_detected_version',
        'version_source': 'harbor_system_info',
        'default_contract_profile': 'harbor-api-v2-core-v1',
        'qualification_floor': '2.4.1',
        'qualification_ceiling_exclusive': '2.16',
    }


def test_harbor_version_bands_resolve_to_one_stable_api_contract() -> None:
    extended = resolve_qualification('harbor', '2.4.1')
    current = resolve_qualification('harbor', '2.15.2')
    future = resolve_qualification('harbor', '2.16.0')

    assert extended is not None
    assert extended.key == 'harbor-extended'
    assert current is not None
    assert current.key == 'harbor-current'
    assert future is None

    for version in ('2.4.1', '2.15.2', '2.16.0'):
        profile = resolve_contract_profile('harbor', version)
        assert profile is not None
        assert profile.key == 'harbor-api-v2-core-v1'


def test_harbor_current_release_requires_live_core_capabilities() -> None:
    result = evaluate_compatibility('harbor', '2.15.2', capabilities=CORE_CAPABILITIES)

    assert result.status == 'compatible'
    assert result.readiness == 'ready'
    assert result.support_level == 'current'
    assert result.qualification_key == 'harbor-current'
    assert result.profile_key == 'harbor-api-v2-core-v1'


def test_harbor_anchor_release_is_extended_and_pre_window_is_eol() -> None:
    extended = evaluate_compatibility('harbor', '2.4.1', capabilities=CORE_CAPABILITIES)
    eol = evaluate_compatibility('harbor', '2.4.0', capabilities=CORE_CAPABILITIES)

    assert extended.status == 'compatible_with_warnings'
    assert extended.readiness == 'degraded'
    assert extended.support_level == 'extended_supported'

    assert eol.status == 'end_of_life'
    assert eol.readiness == 'blocked'
    assert eol.support_level == 'end_of_life'


def test_future_harbor_release_is_unverified_when_core_contract_still_passes() -> None:
    result = evaluate_compatibility('harbor', '2.16.0', capabilities=CORE_CAPABILITIES)

    assert result.status == 'unverified_version'
    assert result.readiness == 'degraded'
    assert result.support_level == 'unverified'
    assert result.qualification_key is None


def test_harbor_capability_mismatch_blocks_even_current_version() -> None:
    result = evaluate_compatibility(
        'harbor',
        '2.15.2',
        capabilities=CORE_CAPABILITIES - {'repository_discovery'},
    )

    assert result.status == 'capability_mismatch'
    assert result.readiness == 'blocked'
    assert result.missing_capabilities == ('repository_discovery',)


def test_registry_provider_contract_is_read_oriented_and_provider_neutral() -> None:
    document = integration_provider_document('registry')
    capabilities = {item['key']: item for item in document['capabilities']}
    products = {item['key']: item for item in document['products']}

    assert document['capability_profile'] == 'registry-provider-read-v1'
    assert set(document['core_capability_keys']) == CORE_CAPABILITIES
    assert CORE_CAPABILITIES.issubset(capabilities)
    assert {
        'artifact_discovery',
        'vulnerability_read',
        'retention_read',
        'immutability_read',
        'signature_metadata',
        'sbom_metadata',
        'webhook_readiness',
        'metrics_readiness',
    }.issubset(capabilities)

    harbor = products['harbor']
    assert harbor['adapter_key'] == 'harbor_api_v2'
    assert harbor['protocol'] == 'harbor_api_v2'
    assert harbor['compatibility_profiles'] == ['harbor-api-v2-core-v1']

    explicit_http_probes = [
        str(item.get('probe') or '').strip()
        for item in capabilities.values()
        if str(item.get('probe') or '').strip().startswith(('GET ', 'POST ', 'PUT ', 'PATCH ', 'DELETE '))
    ]
    assert explicit_http_probes
    assert all(probe.startswith('GET ') for probe in explicit_http_probes)
