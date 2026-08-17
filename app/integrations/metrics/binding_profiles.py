from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Literal

from app.definitions.integration_registry import integration_provider_document
from app.definitions.validation import require_list, require_mapping, require_str

ValidationStrategy = Literal['probe', 'custom']


@dataclass(frozen=True, slots=True)
class BindingProbe:
    expression: str
    signal_key: str
    label: str


@dataclass(frozen=True, slots=True)
class BindingValidationProfile:
    adapter_key: str
    asset_type: str
    profile_key: str
    label: str
    probes: tuple[BindingProbe, ...]
    no_match_message: str
    consumer_family: str = 'metrics'
    validation_strategy: ValidationStrategy = 'probe'


_PROFILES: dict[tuple[str, str], BindingValidationProfile] = {}
_LOCK = RLock()


def register_binding_validation_profile(
    profile: BindingValidationProfile,
    *,
    replace: bool = False,
) -> None:
    adapter_key = str(profile.adapter_key or '').strip().lower()
    asset_type = str(profile.asset_type or '').strip()
    profile_key = str(profile.profile_key or '').strip()
    if not adapter_key:
        raise ValueError('Metrics-source binding validation profile requires an adapter_key.')
    if not asset_type:
        raise ValueError('Metrics-source binding validation profile requires an asset_type.')
    if not profile_key:
        raise ValueError('Metrics-source binding validation profile requires a profile_key.')
    if profile.validation_strategy == 'probe' and not profile.probes:
        raise ValueError(f'Metrics-source binding validation profile {asset_type!r} requires at least one probe.')
    if profile.validation_strategy == 'custom' and profile.probes:
        raise ValueError(
            f'Custom Metrics-source binding validation profile {asset_type!r} must not declare generic probes.'
        )
    with _LOCK:
        key = (adapter_key, asset_type)
        if key in _PROFILES and not replace:
            raise ValueError(f'Metrics-source binding validation profile {key!r} is already registered.')
        _PROFILES[key] = profile


def get_binding_validation_profile(adapter_key: str, asset_type: str) -> BindingValidationProfile | None:
    return _PROFILES.get((str(adapter_key or '').strip().lower(), str(asset_type or '').strip()))


def registered_binding_validation_profiles() -> tuple[BindingValidationProfile, ...]:
    return tuple(_PROFILES[key] for key in sorted(_PROFILES))


def _load_profiles() -> tuple[BindingValidationProfile, ...]:
    document = integration_provider_document('metrics_source')
    profiles: list[BindingValidationProfile] = []
    for profile_index, raw_profile in enumerate(
        require_list(document.get('binding_profiles'), 'metrics_source.binding_profiles')
    ):
        item = require_mapping(raw_profile, f'metrics_source.binding_profiles[{profile_index}]')
        probes: list[BindingProbe] = []
        for probe_index, raw_probe in enumerate(
            require_list(item.get('probes'), f'metrics_source.binding_profiles[{profile_index}].probes')
        ):
            probe = require_mapping(
                raw_probe, f'metrics_source.binding_profiles[{profile_index}].probes[{probe_index}]'
            )
            probes.append(
                BindingProbe(
                    expression=require_str(
                        probe, 'expression', f'metrics_source.binding_profiles[{profile_index}].probes[{probe_index}]'
                    ),
                    signal_key=require_str(
                        probe, 'signal_key', f'metrics_source.binding_profiles[{profile_index}].probes[{probe_index}]'
                    ),
                    label=require_str(
                        probe, 'label', f'metrics_source.binding_profiles[{profile_index}].probes[{probe_index}]'
                    ),
                )
            )
        validation_strategy = require_str(
            item, 'validation_strategy', f'metrics_source.binding_profiles[{profile_index}]'
        )
        if validation_strategy not in {'probe', 'custom'}:
            raise ValueError(f'Unsupported metrics-source binding validation strategy: {validation_strategy!r}.')
        profiles.append(
            BindingValidationProfile(
                adapter_key=require_str(item, 'adapter_key', f'metrics_source.binding_profiles[{profile_index}]'),
                asset_type=require_str(item, 'asset_type', f'metrics_source.binding_profiles[{profile_index}]'),
                profile_key=require_str(item, 'profile_key', f'metrics_source.binding_profiles[{profile_index}]'),
                label=require_str(item, 'label', f'metrics_source.binding_profiles[{profile_index}]'),
                probes=tuple(probes),
                no_match_message=require_str(
                    item, 'no_match_message', f'metrics_source.binding_profiles[{profile_index}]'
                ),
                consumer_family=require_str(
                    item, 'consumer_family', f'metrics_source.binding_profiles[{profile_index}]'
                ),
                validation_strategy=validation_strategy,  # type: ignore[arg-type]
            )
        )
    return tuple(profiles)


for _profile in _load_profiles():
    register_binding_validation_profile(_profile)
