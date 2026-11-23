"""Fail-closed host asset input policy; no external reads or registration route (#5161).

This validates identity and non-production endpoint intent only. It cannot
verify SSH trust, resolve secret references or authorize Ansible execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.infrastructure_automation.inventory_intent import _private_ipv4

_ALLOWED_ENVIRONMENTS = frozenset(
    {'development', 'testing', 'staging', 'laboratory', 'sandbox', 'proof_of_concept', 'non_production'}
)
_IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}\Z')
_SITE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z')


@dataclass(frozen=True, slots=True)
class HostAssetRegistrationIntent:
    asset_key: str
    name: str
    site_key: str
    environment: str
    management_ipv4: str
    ssh_port: int


def validate_host_asset_intent(intent: object) -> str | None:
    """Return a non-sensitive error code; None only for a syntactically valid candidate."""
    if type(intent) is not HostAssetRegistrationIntent:
        return 'HOST_INPUT_UNQUALIFIED'
    if type(intent.asset_key) is not str or _IDENTIFIER.fullmatch(intent.asset_key) is None:
        return 'HOST_IDENTITY_UNQUALIFIED'
    if type(intent.name) is not str or not 1 <= len(intent.name) <= 180 or intent.name.strip() != intent.name:
        return 'HOST_NAME_UNQUALIFIED'
    if any(ord(char) < 32 for char in intent.name):
        return 'HOST_NAME_UNQUALIFIED'
    if type(intent.site_key) is not str or _SITE.fullmatch(intent.site_key) is None:
        return 'HOST_SITE_UNQUALIFIED'
    if type(intent.environment) is not str or intent.environment not in _ALLOWED_ENVIRONMENTS:
        return 'NON_PRODUCTION_ONLY'
    if _private_ipv4(intent.management_ipv4) is None:
        return 'HOST_ENDPOINT_UNQUALIFIED'
    if type(intent.ssh_port) is not int or not 1 <= intent.ssh_port <= 65535:
        return 'HOST_ENDPOINT_UNQUALIFIED'
    return None
