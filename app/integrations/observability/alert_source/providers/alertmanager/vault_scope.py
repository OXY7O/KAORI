"""Strict Vault Alert Source scope admission on the existing Alertmanager binding."""

from __future__ import annotations

from app.extensions.db import db
from app.integrations.binding_selectors import parse_matchers
from app.models.integration import IntegrationInstance

# Match the existing canonical Metrics Source identity convention.
VAULT_ALERT_IDENTITY_LABEL = 'vault_instance'


def require_vault_alert_scope(*, asset_key: str, selector_json: dict | None) -> None:
    key = str(asset_key or '').strip()
    if not key.isascii() or not key.isdecimal() or len(key) > 10:
        raise ValueError('Vault alert bindings require a canonical instance identity.')
    identity = db.session.get(IntegrationInstance, int(key))
    if (
        identity is None
        or identity.integration_type != 'secrets_pki'
        or identity.provider_key != 'vault'
        or not identity.enabled
        or identity.lifecycle_status != 'active'
    ):
        raise ValueError('Vault alert binding references an ineligible provider identity.')
    raw = selector_json.get('matchers') if isinstance(selector_json, dict) else None
    matchers = parse_matchers(selector_json)
    if (
        not isinstance(raw, list)
        or len(raw) != 1
        or len(matchers) != 1
        or matchers[0].label != VAULT_ALERT_IDENTITY_LABEL
        or matchers[0].operator != '='
        or matchers[0].value != str(identity.id)
    ):
        raise ValueError(
            'Vault Alert Source requires an exact vault_instance selector for the canonical KAORI instance.'
        )
