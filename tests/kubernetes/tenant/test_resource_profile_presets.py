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

    quota, limits, customized = _namespace_allocation_values(profile)

    assert quota == RESOURCE_PROFILE_PRESETS['standard']['quota']
    assert limits == RESOURCE_PROFILE_PRESETS['standard']['limits']
    assert customized is False


def test_namespace_allocation_uses_committed_custom_profile_snapshot() -> None:
    profile = SimpleNamespace(
        profile_class='custom',
        quota_hard_json={'requests.cpu': '3'},
        limit_defaults_json={'default': {'cpu': '750m'}},
    )

    quota, limits, customized = _namespace_allocation_values(profile)

    assert quota == {'requests.cpu': '3'}
    assert limits == {'default': {'cpu': '750m'}}
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

    quota, limits, customized = _namespace_allocation_values(profile)

    assert quota == {
        'requests.cpu': RESOURCE_PROFILE_PRESETS['standard']['quota']['requests.cpu'],
        'pods': RESOURCE_PROFILE_PRESETS['standard']['quota']['pods'],
    }
    assert limits == {
        'default': {'cpu': RESOURCE_PROFILE_PRESETS['standard']['limits']['default']['cpu']}
    }
    assert customized is False

def test_advanced_profile_controls_are_explicit_persisted_intent() -> None:
    controls = _advanced_profile_controls(
        {
            'advanced_control_contract_present': '1',
            'advanced_control_ingress': 'on',
            'advanced_control_managed_tls': '1',
            'advanced_control_capsule_resource_pools': 'true',
        }
    )

    assert set(controls) == set(RESOURCE_PROFILE_ADVANCED_CONTROLS)
    assert controls['ingress'] is True
    assert controls['service_exposure'] is False
    assert controls['managed_tls'] is True
    assert controls['capsule_resource_pools'] is True
    assert controls['hostname_reservation'] is False
    assert controls['managed_registry'] is False


def test_advanced_profile_controls_are_gated_by_provider_capability() -> None:
    controls = {
        'ingress': True,
        'managed_tls': True,
        'capsule_resource_pools': True,
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
    assert state['managed_tls']['state'] == 'unsupported'
    assert state['capsule_resource_pools']['state'] == 'unsupported'
    assert state['hostname_reservation']['state'] == 'disabled'


def test_capsule_advanced_control_requires_specific_capsule_capability() -> None:
    state = evaluate_resource_profile_advanced_controls(
        {'capsule_resource_pools': True},
        provider_key='capsule',
        capability_statuses={'resource_pools': 'available'},
    )

    assert state['capsule_resource_pools']['state'] == 'enabled'
    assert state['capsule_resource_pools']['requested'] is True

