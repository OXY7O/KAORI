from types import SimpleNamespace

from app.kubernetes.tenant.service import (
    RESOURCE_PROFILE_ADVANCED_CONTROLS,
    RESOURCE_PROFILE_PRESETS,
    _advanced_profile_controls,
    _namespace_allocation_values,
    _profile_values,
    _resource_profile_values,
    evaluate_resource_profile_advanced_controls,
)


def test_standard_preset_exposes_canonical_versioned_values() -> None:
    standard = RESOURCE_PROFILE_PRESETS['standard']

    assert standard['version'] == 1
    assert standard['quota']['requests.cpu'] == '2'
    assert standard['quota']['requests.memory'] == '4Gi'
    assert standard['limits']['default']['cpu'] == '500m'
    assert standard['limits']['default_request']['memory'] == '128Mi'


def test_builtin_preset_ignores_submitted_resource_overrides() -> None:
    quota, limits, version, base_class, base_version = _resource_profile_values(
        'standard',
        {
            'requests_cpu': '99',
            'requests_memory': '99Gi',
            'default_cpu': '99',
        },
    )

    assert quota == RESOURCE_PROFILE_PRESETS['standard']['quota']
    assert limits == RESOURCE_PROFILE_PRESETS['standard']['limits']
    assert version == RESOURCE_PROFILE_PRESETS['standard']['version']
    assert base_class is None
    assert base_version is None


def test_custom_profile_accepts_values_and_preserves_base_preset_lineage() -> None:
    quota, limits, version, base_class, base_version = _resource_profile_values(
        'custom',
        {
            'base_preset_class': 'standard',
            'requests_cpu': '3',
            'requests_memory': '6Gi',
            'default_cpu': '750m',
        },
    )

    assert quota == {'requests.cpu': '3', 'requests.memory': '6Gi'}
    assert limits == {'default': {'cpu': '750m'}}
    assert version == 1
    assert base_class == 'standard'
    assert base_version == RESOURCE_PROFILE_PRESETS['standard']['version']


def test_blank_custom_profile_dimensions_are_explicitly_unbounded() -> None:
    quota, limits = _profile_values({})

    assert quota == {}
    assert limits == {}


def test_namespace_allocation_uses_canonical_builtin_snapshot() -> None:
    profile = SimpleNamespace(
        profile_class='standard',
        quota_hard_json={'requests.cpu': '99'},
        limit_defaults_json={'default': {'cpu': '99'}},
    )

    quota, limits, storage_policy, customized = _namespace_allocation_values(profile)

    assert quota == RESOURCE_PROFILE_PRESETS['standard']['quota']
    assert limits == RESOURCE_PROFILE_PRESETS['standard']['limits']
    assert storage_policy == {}
    assert customized is False


def test_namespace_allocation_uses_committed_custom_profile_snapshot() -> None:
    profile = SimpleNamespace(
        profile_class='custom',
        quota_hard_json={'requests.cpu': '3'},
        limit_defaults_json={'default': {'cpu': '750m'}},
    )

    quota, limits, storage_policy, customized = _namespace_allocation_values(profile)

    assert quota == {'requests.cpu': '3'}
    assert limits == {'default': {'cpu': '750m'}}
    assert storage_policy == {}
    assert customized is True



def test_extra_large_preset_exposes_canonical_fixed_values() -> None:
    extra_large = RESOURCE_PROFILE_PRESETS['extra_large']

    assert extra_large['version'] == 1
    assert extra_large['quota']['requests.cpu'] == '8'
    assert extra_large['quota']['requests.memory'] == '16Gi'
    assert extra_large['quota']['requests.storage'] == '400Gi'


def test_builtin_preset_control_mask_keeps_values_fixed_and_omits_unmanaged_dimensions() -> None:
    quota, limits, version, base_class, base_version = _resource_profile_values(
        'standard',
        {
            'control_contract_present': '1',
            'control_requests_cpu': '1',
            'control_requests_memory': '1',
            'control_default_cpu': '1',
            'requests_cpu': '99',
            'requests_memory': '99Gi',
            'default_cpu': '99',
        },
    )

    assert quota == {
        'requests.cpu': RESOURCE_PROFILE_PRESETS['standard']['quota']['requests.cpu'],
        'requests.memory': RESOURCE_PROFILE_PRESETS['standard']['quota']['requests.memory'],
    }
    assert limits == {
        'default': {'cpu': RESOURCE_PROFILE_PRESETS['standard']['limits']['default']['cpu']}
    }
    assert version == RESOURCE_PROFILE_PRESETS['standard']['version']
    assert base_class is None
    assert base_version is None


def test_namespace_builtin_snapshot_uses_stored_control_mask_with_canonical_values() -> None:
    profile = SimpleNamespace(
        profile_class='standard',
        quota_hard_json={'requests.cpu': '999', 'pods': '999'},
        limit_defaults_json={'default': {'cpu': '999'}},
    )

    quota, limits, storage_policy, customized = _namespace_allocation_values(profile)

    assert quota == {
        'requests.cpu': RESOURCE_PROFILE_PRESETS['standard']['quota']['requests.cpu'],
        'pods': RESOURCE_PROFILE_PRESETS['standard']['quota']['pods'],
    }
    assert limits == {
        'default': {'cpu': RESOURCE_PROFILE_PRESETS['standard']['limits']['default']['cpu']}
    }
    assert storage_policy == {}
    assert customized is False

def test_advanced_profile_controls_persist_real_values() -> None:
    controls = _advanced_profile_controls(
        {
            'advanced_control_contract_present': '1',
            'advanced_control_ingress': 'on',
            'advanced_control_ingress_enforcement_mode': 'required',
            'advanced_control_service_exposure': 'on',
            'advanced_control_service_exposure_profile_key': 'custom',
            'advanced_control_service_exposure_allow_cluster_ip': 'allow',
            'advanced_control_service_exposure_allow_ingress': 'allow',
            'advanced_control_service_exposure_allow_node_port': 'deny',
            'advanced_control_service_exposure_allow_load_balancer': 'deny',
            'advanced_control_service_exposure_allow_external_name': 'deny',
            'advanced_control_hostname_reservation': 'on',
            'advanced_control_hostname_reservation_match_mode': 'wildcard',
            'advanced_control_hostname_reservation_hostname_pattern': '*.example.com',
            'advanced_control_managed_tls': '1',
            'advanced_control_managed_tls_mode': 'platform_tls',
            'advanced_control_managed_tls_resource_name': 'tenant-tls',
            'advanced_control_capsule_resource_pools': 'true',
            'advanced_control_capsule_resource_pools_resource_kind': 'resource_pool',
            'advanced_control_capsule_resource_pools_resource_name': 'team-pool',
            'advanced_control_capsule_resource_pools_spec_json': '{"quota":{"hard":{"requests.cpu":"4"}}}',
        }
    )

    assert controls['ingress'] == {
        'enabled': True,
        'enforcement_required': True,
    }
    assert controls['service_exposure'] == {
        'enabled': True,
        'profile_key': 'custom',
        'allow_cluster_ip': True,
        'allow_ingress': True,
        'allow_node_port': False,
        'allow_load_balancer': False,
        'allow_external_name': False,
    }
    assert controls['hostname_reservation'] == {
        'enabled': True,
        'match_mode': 'wildcard',
        'hostname_pattern': '*.example.com',
    }
    assert controls['managed_tls'] == {
        'enabled': True,
        'mode': 'platform_tls',
        'resource_name': 'tenant-tls',
        'source_reference': None,
    }
    assert controls['capsule_resource_pools'] == {
        'enabled': True,
        'resource_kind': 'resource_pool',
        'resource_name': 'team-pool',
        'spec': {'quota': {'hard': {'requests.cpu': '4'}}},
    }


def test_advanced_profile_controls_are_gated_by_provider_capability_and_keep_configuration() -> None:
    controls = {
        'ingress': {'enabled': True, 'enforcement_required': True},
        'managed_tls': {'enabled': True, 'mode': 'platform_tls', 'resource_name': 'tenant-tls'},
        'capsule_resource_pools': {
            'enabled': True,
            'resource_kind': 'resource_pool',
            'resource_name': 'team-pool',
            'spec': {'quota': {'hard': {'requests.cpu': '4'}}},
        },
    }
    state = evaluate_resource_profile_advanced_controls(
        controls,
        provider_key='native_kubernetes',
        capability_statuses={
            'service_exposure_preflight': 'available',
            'admission_enforcement': 'available',
            'managed_tls': 'unavailable',
        },
    )

    assert state['ingress']['state'] == 'enabled'
    assert state['ingress']['configuration'] == {'enforcement_required': True}
    assert state['managed_tls']['state'] == 'unsupported'
    assert state['capsule_resource_pools']['state'] == 'unsupported'
    assert state['hostname_reservation']['state'] == 'disabled'


def test_capsule_advanced_control_requires_specific_capsule_capability() -> None:
    state = evaluate_resource_profile_advanced_controls(
        {
            'capsule_resource_pools': {
                'enabled': True,
                'resource_kind': 'resource_pool',
                'resource_name': 'team-pool',
                'spec': {'quota': {'hard': {'requests.cpu': '4'}}},
            }
        },
        provider_key='capsule',
        capability_statuses={'resource_pools': 'available'},
    )

    assert state['capsule_resource_pools']['state'] == 'enabled'
    assert state['capsule_resource_pools']['requested'] is True
    assert state['capsule_resource_pools']['configuration']['resource_name'] == 'team-pool'



def test_custom_profile_storage_policy_is_managed_and_validated() -> None:
    from app.kubernetes.tenant.service import _storage_policy_values

    policy = _storage_policy_values(
        {
            'control_contract_present': '1',
            'control_pvc_min_storage': '1',
            'pvc_min_storage': '1Gi',
            'control_pvc_max_storage': '1',
            'pvc_max_storage': '10Gi',
            'control_pvc_default_request_storage': '1',
            'pvc_default_request_storage': '2Gi',
        }
    )

    assert policy == {
        'min': '1Gi',
        'max': '10Gi',
        'default_request': '2Gi',
    }


def test_storage_policy_rejects_min_greater_than_max() -> None:
    import pytest
    from app.kubernetes.tenant.validation import validate_storage_policy

    with pytest.raises(ValueError, match='minimum storage cannot exceed maximum storage'):
        validate_storage_policy({'min': '20Gi', 'max': '10Gi'})
