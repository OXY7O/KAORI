"""Bounded capability-level public Vault PKI expiry pressure for Central Intelligence.

Source is the committed, generation-qualified stored-certificate aggregate.
Never surface a Secret, Vault mount, namespace, serial, fingerprint or provider
identity here. Per-asset findings require separately admitted source scoping.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from app.secrets_pki.pki_validity_posture import build_stored_pki_validity_posture

_RULE_KEY = 'secrets_pki.pki.stored_certificate_expiry_pressure'
_VALIDITY_REVIEW_RULE_KEY = 'secrets_pki.pki.stored_certificate_validity_review'
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
    """Return qualified population-wide findings, never per-certificate data."""
    rule = rules.get(_RULE_KEY)
    validity_rule = rules.get(_VALIDITY_REVIEW_RULE_KEY)
    if rule is None and validity_rule is None:
        return []

    snapshot = build_stored_pki_validity_posture()
    if snapshot.get('status') != 'ready':
        # Unknown/stale/partial is not zero evidence or an assertion of safety.
        return []
    unvalidated_counts = {key: snapshot.get(key) for key in _COUNT_KEYS}
    if any(type(value) is not int or value < 0 for value in unvalidated_counts.values()):
        return []
    counts = cast(dict[str, int], unvalidated_counts)
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

    findings: list[dict[str, Any]] = []
    if rule is not None:
        findings.extend(_expiry_findings(rule, counts, observed_at))
    if validity_rule is not None and counts['unknown'] > 0:
        findings.append(_validity_review_finding(validity_rule, counts, observed_at))
    return findings


def _expiry_findings(rule: dict[str, Any], counts: dict[str, int], observed_at: datetime) -> list[dict[str, Any]]:
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


def _validity_review_finding(rule: dict[str, Any], counts: dict[str, int], observed_at: datetime) -> dict[str, Any]:
    unknown = counts['unknown']
    return {
        **rule,
        'rule_key': f'{_VALIDITY_REVIEW_RULE_KEY}:population',
        'title': 'Stored Public PKI Validity Evidence Needs Review',
        'severity': 'warning',
        'priority': 'P2',
        'status': 'available',
        'summary': f'{unknown} observed stored public certificates have unclassified validity windows.',
        'condition_summary': 'Qualified committed observations include absent or incoherent validity bounds.',
        'recommended_action': (
            'Review the authorized PKI inventory and public certificate metadata; '
            'verify validity bounds independently before planning renewal or remediation.'
        ),
        'evidence': {
            'asset_key': _ASSET_KEY,
            'source_status': 'ready',
            'source_coverage': 'Opted-in stored public Vault PKI certificates only',
            'observed_at': observed_at.isoformat(),
            'observed_stored_certificates': counts['observed_stored_certificates'],
            'unclassified_validity_windows': unknown,
            'trust_verified': False,
            'revocation_verified': False,
            'endpoint_serving_verified': False,
        },
    }
