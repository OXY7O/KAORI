from __future__ import annotations

from app.definitions.integration_registry import integration_provider_document
from app.definitions.validation import require_list, require_mapping, require_str, string_tuple
from app.integrations.alertmanager.profiles.base import AlertmanagerProfile


def _load_profiles() -> tuple[AlertmanagerProfile, ...]:
    document = integration_provider_document('alertmanager')
    profiles: list[AlertmanagerProfile] = []
    for index, raw in enumerate(require_list(document.get('profiles'), 'alertmanager.profiles')):
        item = require_mapping(raw, f'alertmanager.profiles[{index}]')
        profiles.append(
            AlertmanagerProfile(
                key=require_str(item, 'key', f'alertmanager.profiles[{index}]'),
                version_constraint=require_str(item, 'version_constraint', f'alertmanager.profiles[{index}]'),
                support_level=require_str(item, 'support_level', f'alertmanager.profiles[{index}]'),
                required_capabilities=string_tuple(
                    item.get('required_capabilities'),
                    f'alertmanager.profiles[{index}].required_capabilities',
                ),
                known_limitations=string_tuple(
                    item.get('known_limitations'),
                    f'alertmanager.profiles[{index}].known_limitations',
                ),
            )
        )
    return tuple(profiles)


PROFILES = _load_profiles()
PROFILES_BY_KEY = {profile.key: profile for profile in PROFILES}


def get_profile_by_key(key: str) -> AlertmanagerProfile:
    try:
        return PROFILES_BY_KEY[key]
    except KeyError as exc:
        raise ValueError(f'Unknown Alertmanager compatibility profile: {key!r}.') from exc
