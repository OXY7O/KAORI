"""Bounded capability-level public Vault PKI expiry pressure for Central Intelligence.

Source is the committed, generation-qualified stored-certificate aggregate.
Never surface a Secret, Vault mount, namespace, serial, fingerprint or provider
identity here. Per-asset findings require separately admitted source scoping.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.secrets_pki.pki_validity_posture import build_stored_pki_validity_posture

_RULE_KEY = 'secrets_pki.pki.stored_certificate_expiry_pressure'
_ASSET_KEY = 'secrets_pki:stored_public_certificates'
_COUNT_KEYS = (
    'observed_stored_certificates',
    'within_validity_window',
    'not_yet_valid',
    'expired',
    'unknown',
    'expires_within_7d',
    'expires_8_to_30d',
    'expires_after_30d',
)


def build_secrets_pki_recommendation_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one actionable population-wide finding, never per-certificate data."""
    rule = rules.get(_RULE_KEY)
    if rule is None:
        return []

    snapshot = build_stored_pki_validity_posture()
    if snapshot.get('status') != 'ready':
        # Unknown/stale/partial is not zero evidence or an assertion of safety.
        return []
    counts = {key: snapshot.get(key) for key in _COUNT_KEYS}
    if any(type(value) is not int or value < 0 for value in counts.values()):
        return []
    if (
        counts['observed_stored_certificates']
        != counts['within_validity_window'] + counts['not_yet_valid'] + counts['expired'] + counts['unknown']
        or counts['within_validity_window']
        != counts['expires_within_7d'] + counts['expires_8_to_30d'] + counts['expires_after_30d']
    ):
        return []
    observed_at = snapshot.get('last_observed_at')
    if not isinstance(observed_at, datetime) or observed_at.tzinfo is None or observed_at.utcoffset() is None:
        return []

    expired = counts['expired']
    imminent = counts['expires_within_7d']
    approaching = counts['expires_8_to_30d']
    if expired:
        severity, priority, label = 'critical', 'P1', 'expired'
    elif imminent:
        severity, priority, label = 'warning', 'P2', 'expiring within 7 days'
    elif approaching:
        severity, priority, label = 'info', 'P3', 'expiring within 8 to 30 days'
    else:
        return []

    # Deliberately one immutable capability/population identity: no source
    # instance, public fingerprint, mount or resource selector is exported.
    return [
        {
            **rule,
            'rule_key': f'{_RULE_KEY}:population',
            'title': 'Stored Public PKI Certificates Need Expiry Review',
            'severity': severity,
            'priority': priority,
            'status': 'available',
            'summary': (
                f'Qualified opted-in Vault stored-public-certificate evidence includes '
                f'{expired} expired, {imminent} within 7 days and {approaching} within 8–30 days.'
            ),
            'condition_summary': f'The qualified population includes public certificates {label}.',
            'recommended_action': (
                'Review the authorized Vault PKI sources, identify affected certificate owners, '
                'and verify renewal, consumer cutover and actual endpoint status independently.'
            ),
            'evidence': {
                'asset_key': _ASSET_KEY,
                'source_status': 'ready',
                'source_coverage': 'Opted-in stored public Vault PKI certificates only',
                'observed_at': observed_at.isoformat(),
                'observed_stored_certificates': counts['observed_stored_certificates'],
                'expired': expired,
                'expires_within_7d': imminent,
                'expires_8_to_30d': approaching,
                'trust_verified': False,
                'revocation_verified': False,
                'endpoint_serving_verified': False,
            },
        }
    ]
