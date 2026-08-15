from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from app.definitions.integration_registry import integration_provider_document
from app.definitions.validation import require_list, require_mapping, require_str, string_tuple


@dataclass(frozen=True, slots=True)
class AlertConsumerProfile:
    asset_type: str
    profile_key: str
    label: str
    required_capabilities: tuple[str, ...]
    optional_capabilities: tuple[str, ...] = ()
    no_match_message: str = ''
    consumer_family: str = 'alerts'
    selector_hint: str = ''


_PROFILES: dict[str, AlertConsumerProfile] = {}
_LOCK = RLock()


def register_alert_consumer_profile(
    profile: AlertConsumerProfile,
    *,
    replace: bool = False,
) -> None:
    asset_type = str(profile.asset_type or '').strip()
    profile_key = str(profile.profile_key or '').strip()
    if not asset_type:
        raise ValueError('Alertmanager consumer profile requires an asset_type.')
    if not profile_key:
        raise ValueError('Alertmanager consumer profile requires a profile_key.')
    if not profile.required_capabilities:
        raise ValueError(f'Alertmanager consumer profile {profile_key!r} requires capability evidence.')
    with _LOCK:
        if asset_type in _PROFILES and not replace:
            raise ValueError(f'Alertmanager consumer profile for {asset_type!r} is already registered.')
        _PROFILES[asset_type] = profile


def get_alert_consumer_profile(asset_type: str) -> AlertConsumerProfile | None:
    return _PROFILES.get(str(asset_type or '').strip())


def registered_alert_consumer_profiles() -> tuple[AlertConsumerProfile, ...]:
    return tuple(_PROFILES[key] for key in sorted(_PROFILES))


def _load_profiles() -> tuple[AlertConsumerProfile, ...]:
    document = integration_provider_document('alertmanager')
    profiles: list[AlertConsumerProfile] = []
    for index, raw in enumerate(require_list(document.get('consumer_profiles'), 'alertmanager.consumer_profiles')):
        item = require_mapping(raw, f'alertmanager.consumer_profiles[{index}]')
        profiles.append(
            AlertConsumerProfile(
                asset_type=require_str(item, 'asset_type', f'alertmanager.consumer_profiles[{index}]'),
                profile_key=require_str(item, 'profile_key', f'alertmanager.consumer_profiles[{index}]'),
                label=require_str(item, 'label', f'alertmanager.consumer_profiles[{index}]'),
                required_capabilities=string_tuple(item.get('required_capabilities'), f'alertmanager.consumer_profiles[{index}].required_capabilities'),
                optional_capabilities=string_tuple(item.get('optional_capabilities'), f'alertmanager.consumer_profiles[{index}].optional_capabilities'),
                no_match_message=require_str(item, 'no_match_message', f'alertmanager.consumer_profiles[{index}]'),
                consumer_family=require_str(item, 'consumer_family', f'alertmanager.consumer_profiles[{index}]'),
                selector_hint=require_str(item, 'selector_hint', f'alertmanager.consumer_profiles[{index}]'),
            )
        )
    return tuple(profiles)


for _profile in _load_profiles():
    register_alert_consumer_profile(_profile)
