from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Literal

from app.definitions.integration_registry import integration_provider_document
from app.definitions.validation import require_list, require_mapping, require_str

ValidationStrategy = Literal['probe', 'custom']


@dataclass(frozen=True, slots=True)
class BindingProbe:
    metric: str
    label: str


@dataclass(frozen=True, slots=True)
class BindingValidationProfile:
    asset_type: str
    profile_key: str
    label: str
    probes: tuple[BindingProbe, ...]
    no_match_message: str
    consumer_family: str = 'metrics'
    validation_strategy: ValidationStrategy = 'probe'


_PROFILES: dict[str, BindingValidationProfile] = {}
_LOCK = RLock()


def register_binding_validation_profile(
    profile: BindingValidationProfile,
    *,
    replace: bool = False,
) -> None:
    asset_type = str(profile.asset_type or '').strip()
    profile_key = str(profile.profile_key or '').strip()
    if not asset_type:
        raise ValueError('Prometheus binding validation profile requires an asset_type.')
    if not profile_key:
        raise ValueError('Prometheus binding validation profile requires a profile_key.')
    if profile.validation_strategy == 'probe' and not profile.probes:
        raise ValueError(f'Prometheus binding validation profile {asset_type!r} requires at least one probe.')
    if profile.validation_strategy == 'custom' and profile.probes:
        raise ValueError(f'Custom Prometheus binding validation profile {asset_type!r} must not declare generic probes.')
    with _LOCK:
        if asset_type in _PROFILES and not replace:
            raise ValueError(f'Prometheus binding validation profile {asset_type!r} is already registered.')
        _PROFILES[asset_type] = profile


def get_binding_validation_profile(asset_type: str) -> BindingValidationProfile | None:
    return _PROFILES.get(str(asset_type or '').strip())


def registered_binding_validation_profiles() -> tuple[BindingValidationProfile, ...]:
    return tuple(_PROFILES[key] for key in sorted(_PROFILES))


def _load_profiles() -> tuple[BindingValidationProfile, ...]:
    document = integration_provider_document('prometheus')
    profiles: list[BindingValidationProfile] = []
    for profile_index, raw_profile in enumerate(require_list(document.get('binding_profiles'), 'prometheus.binding_profiles')):
        item = require_mapping(raw_profile, f'prometheus.binding_profiles[{profile_index}]')
        probes: list[BindingProbe] = []
        for probe_index, raw_probe in enumerate(require_list(item.get('probes'), f'prometheus.binding_profiles[{profile_index}].probes')):
            probe = require_mapping(raw_probe, f'prometheus.binding_profiles[{profile_index}].probes[{probe_index}]')
            probes.append(
                BindingProbe(
                    metric=require_str(probe, 'metric', f'prometheus.binding_profiles[{profile_index}].probes[{probe_index}]'),
                    label=require_str(probe, 'label', f'prometheus.binding_profiles[{profile_index}].probes[{probe_index}]'),
                )
            )
        validation_strategy = require_str(item, 'validation_strategy', f'prometheus.binding_profiles[{profile_index}]')
        if validation_strategy not in {'probe', 'custom'}:
            raise ValueError(f'Unsupported Prometheus binding validation strategy: {validation_strategy!r}.')
        profiles.append(
            BindingValidationProfile(
                asset_type=require_str(item, 'asset_type', f'prometheus.binding_profiles[{profile_index}]'),
                profile_key=require_str(item, 'profile_key', f'prometheus.binding_profiles[{profile_index}]'),
                label=require_str(item, 'label', f'prometheus.binding_profiles[{profile_index}]'),
                probes=tuple(probes),
                no_match_message=require_str(item, 'no_match_message', f'prometheus.binding_profiles[{profile_index}]'),
                consumer_family=require_str(item, 'consumer_family', f'prometheus.binding_profiles[{profile_index}]'),
                validation_strategy=validation_strategy,  # type: ignore[arg-type]
            )
        )
    return tuple(profiles)


for _profile in _load_profiles():
    register_binding_validation_profile(_profile)
