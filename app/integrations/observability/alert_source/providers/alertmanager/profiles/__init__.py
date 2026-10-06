from __future__ import annotations

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from app.integrations.compatibility import normalize_runtime_version
from app.integrations.observability.alert_source.providers.alertmanager.profiles.alertmanager_v025 import (
    PROFILE as ALERTMANAGER_V025,
)
from app.integrations.observability.alert_source.providers.alertmanager.profiles.alertmanager_v033 import (
    PROFILE as ALERTMANAGER_V033,
)
from app.integrations.observability.alert_source.providers.alertmanager.profiles.base import AlertmanagerProfile

PROFILES: tuple[AlertmanagerProfile, ...] = (ALERTMANAGER_V025, ALERTMANAGER_V033)


def resolve_profile(version: str | None) -> AlertmanagerProfile | None:
    if not version:
        return None
    try:
        parsed = Version(normalize_runtime_version(version))
    except InvalidVersion:
        return None
    return next((profile for profile in PROFILES if parsed in SpecifierSet(profile.version_constraint)), None)
