from __future__ import annotations

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from app.alertmanager.profiles.alertmanager_v025 import PROFILE as ALERTMANAGER_V025
from app.alertmanager.profiles.alertmanager_v033 import PROFILE as ALERTMANAGER_V033
from app.alertmanager.profiles.base import AlertmanagerProfile
from app.integrations.compatibility import normalize_runtime_version

PROFILES: tuple[AlertmanagerProfile, ...] = (ALERTMANAGER_V025, ALERTMANAGER_V033)


def resolve_profile(version: str | None) -> AlertmanagerProfile | None:
    if not version:
        return None
    try:
        parsed = Version(normalize_runtime_version(version))
    except InvalidVersion:
        return None
    return next((profile for profile in PROFILES if parsed in SpecifierSet(profile.version_constraint)), None)
