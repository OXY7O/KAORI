"""Independent reviewer/successor session-attestation boundary for Capsule #1229.

The pure inspector checks signatures' TARGET and asserted session shape;
it cannot authenticate a real human, MFA challenge or IdP. The staged
MAC checker is deliberately unregistered and source-disabled before any
backend key access. Its future caller must use an authenticated server-side
IdP/key policy, never accept a browser-provided signing key.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from app.kubernetes.tenant.capsule_handoff_related_inventory import _canonical, _digest
from app.kubernetes.tenant.capsule_handoff_resource_consent import (
    inspect_capsule_resource_consent,
)

_SHA = re.compile(r'[a-f0-9]{64}\Z')
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{2,119}\Z')
_VERSION = 'capsule-resource-human-session-attestation/v1'
_ACTIONS = ('independent_review', 'successor_acceptance')
_FIELDS = frozenset({
    'contract_version', 'attestation_id', 'issuer_id', 'key_id',
    'action', 'actor_user_id', 'session_sha256', 'challenge_sha256',
    'authentication_method', 'authenticated_at', 'issued_at', 'expires_at',
    'tenant_id', 'cluster_id', 'generation', 'plan_sha256',
    'worklist_sha256', 'resource_review_sha256',
    'consent_manifest_sha256', 'resource_scope_sha256', 'mac_sha256',
})
_AUTH_METHOD = 'phishing_resistant_mfa'
_MAX_AGE = timedelta(minutes=5)
_MAX_LIFETIME = timedelta(minutes=5)
_IDENTITY_MAC_VERIFIER_ENABLED = False
_AUTHENTICATED_HUMAN_SESSION_INGRESS_ENABLED = False


class CapsuleConsentIssuerKeyBroker(Protocol):
    """Server-owned IdP receipt key source; no implementation is registered."""

    def read_verification_key(self, *, issuer_id: str, key_id: str) -> bytes: ...


class CapsuleConsentIssuerPolicy(Protocol):
    """Independent operator-owned IdP issuer/key identity pin registry."""

    def expected_key_fingerprint(self, *, issuer_id: str, key_id: str) -> str: ...


def _date(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError('Capsule human attestation time must be UTC-aware.')
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('Capsule human attestation timestamp is malformed.') from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('Capsule human attestation lacks a timezone.')
    return parsed.astimezone(UTC)


def inspect_capsule_consent_session_attestations(
    *, plan: Mapping[str, Any], resource_report: Mapping[str, Any],
    approval: Mapping[str, Any], acceptance: Mapping[str, Any],
    manifest: Mapping[str, Any], attestations: list[Mapping[str, Any]],
    expected_issuer_id: str, expected_key_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Require exactly two independent actor-bound, SHA-bound claimed receipts.

    NO signature is verified in this function. A user-provided MAC, session
    hash, factor claim or issuer ID is not authority to enter execution.
    """
    consent = inspect_capsule_resource_consent(
        plan=plan, resource_report=resource_report,
        approval=approval, acceptance=acceptance, manifest=manifest,
    )
    if (
        not isinstance(attestations, list) or len(attestations) != 2
        or not all(isinstance(x, Mapping) and set(x) == _FIELDS for x in attestations)
        or not isinstance(expected_issuer_id, str) or not _ID.fullmatch(expected_issuer_id)
        or not isinstance(expected_key_id, str) or not _ID.fullmatch(expected_key_id)
    ):
        raise ValueError('Capsule consent needs exactly two bounded IdP assertion envelopes.')
    instant = datetime.now(UTC) if now is None else now
    if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError('Capsule attestation freshness requires an aware current time.')
    instant = instant.astimezone(UTC)
    ordered = sorted(attestations, key=lambda x: str(x.get('action')))
    if [x['action'] for x in ordered] != list(_ACTIONS):
        raise ValueError('Capsule human attestation actions must be distinct review and acceptance.')
    # Lexicographic order is independent_review then successor_acceptance.
    expected_ids = (approval.get('approved_by'), acceptance.get('accepted_by'))
    accepted_at = _date(manifest['accepted_at'])
    sessions: set[str] = set()
    challenges: set[str] = set()
    assertion_ids: set[str] = set()
    times: list[datetime] = []
    for index, item in enumerate(ordered):
        try:
            parsed_uuid = UUID(str(item['attestation_id']))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError('Capsule human attestation UUID is invalid.') from exc
        signed_at, expires_at, authenticated_at = (
            _date(item['issued_at']), _date(item['expires_at']),
            _date(item['authenticated_at']),
        )
        if (
            item['contract_version'] != _VERSION
            or str(parsed_uuid) != item['attestation_id']
            or item['attestation_id'] in assertion_ids
            or item['issuer_id'] != expected_issuer_id
            or item['key_id'] != expected_key_id
            or type(item['actor_user_id']) is not int
            or item['actor_user_id'] != expected_ids[index]
            or item['authentication_method'] != _AUTH_METHOD
            or any(not isinstance(item[k], str) or not _SHA.fullmatch(item[k])
                   for k in ('session_sha256', 'challenge_sha256', 'mac_sha256'))
            or item['session_sha256'] in sessions
            or item['challenge_sha256'] in challenges
            or any(item.get(field) != expected for field, expected in (
                ('tenant_id', plan['tenant_id']),
                ('cluster_id', plan['cluster_id']),
                ('generation', plan['generation']),
                ('plan_sha256', plan['plan_sha256']),
                ('worklist_sha256', consent['worklist_sha256']),
                ('resource_review_sha256', consent['resource_review_sha256']),
                ('consent_manifest_sha256', consent['resource_consent_manifest_sha256']),
                ('resource_scope_sha256', consent['resource_scope_sha256']),
            ))
            or not authenticated_at <= signed_at <= instant < expires_at
            or instant - signed_at > _MAX_AGE
            or signed_at - authenticated_at > _MAX_AGE
            or expires_at - signed_at > _MAX_LIFETIME
        ):
            raise ValueError('Capsule consent attestation is stale, duplicated or cross-scope.')
        sessions.add(item['session_sha256'])
        challenges.add(item['challenge_sha256'])
        assertion_ids.add(item['attestation_id'])
        times.append(signed_at)
    reviewed_at = _date(approval.get('approved_at'))
    prior_acceptance_at = _date(acceptance.get('accepted_at'))
    if not (
        reviewed_at <= times[0] <= times[1] <= accepted_at <= instant
        and prior_acceptance_at <= times[1]
    ):
        raise ValueError('Capsule review and successor confirmation chronology is invalid.')
    return {
        'status': 'distinct_idp_session_claims_correlated_not_authenticated',
        'tenant_id': plan['tenant_id'], 'plan_sha256': plan['plan_sha256'],
        'worklist_sha256': consent['worklist_sha256'],
        'resource_review_sha256': consent['resource_review_sha256'],
        'consent_manifest_sha256': consent['resource_consent_manifest_sha256'],
        'session_attestation_digest_sha256': _digest([dict(x) for x in ordered]),
        'attestation_count': len(ordered),
        'distinct_claimed_sessions': True,
        'claimed_authentication_method': _AUTH_METHOD,
        'idp_signer_key_verified': False,
        'idp_session_origin_authenticated': False,
        'mfa_challenge_verified': False,
        'one_time_challenge_consumed': False,
        'consent_source_authenticated': False,
        'independent_consent_record_committed': False,
        'provider_execution_admitted': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }


def review_capsule_consent_idp_mac_staged(
    *, plan: Mapping[str, Any], resource_report: Mapping[str, Any],
    approval: Mapping[str, Any], acceptance: Mapping[str, Any],
    manifest: Mapping[str, Any], attestations: list[Mapping[str, Any]],
    expected_issuer_id: str, expected_key_id: str,
    broker: CapsuleConsentIssuerKeyBroker,
    operator_policy: CapsuleConsentIssuerPolicy,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Unreachable cryptographic check; MAC != real MFA or accepted consent."""
    if not _IDENTITY_MAC_VERIFIER_ENABLED or not _AUTHENTICATED_HUMAN_SESSION_INGRESS_ENABLED:
        raise PermissionError(
            'Capsule consent identity verifier is source-disabled pending '
            'operator-registered IdP and replay-safe step-up authentication.'
        )
    reviewed = inspect_capsule_consent_session_attestations(
        plan=plan, resource_report=resource_report, approval=approval,
        acceptance=acceptance, manifest=manifest, attestations=attestations,
        expected_issuer_id=expected_issuer_id, expected_key_id=expected_key_id, now=now,
    )
    key: bytes | None = None
    try:
        pinned = operator_policy.expected_key_fingerprint(
            issuer_id=expected_issuer_id, key_id=expected_key_id,
        )
        key = broker.read_verification_key(
            issuer_id=expected_issuer_id, key_id=expected_key_id,
        )
        if (
            type(key) is not bytes or len(key) < 32
            or not isinstance(pinned, str) or not _SHA.fullmatch(pinned)
            or not hmac.compare_digest(hashlib.sha256(key).hexdigest(), pinned)
        ):
            raise ValueError('Capsule IdP key is not pinned.')
        for item in attestations:
            payload = {field: item[field] for field in _FIELDS - {'mac_sha256'}}
            expected = hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, item['mac_sha256']):
                raise ValueError('Capsule human assertion MAC differs.')
    except Exception:
        raise ValueError('Capsule consent IdP signature source could not be verified.') from None
    finally:
        key = None
    return {
        **reviewed,
        'status': 'idp_assertion_mac_correlated_upstream_human_auth_unverified',
        'idp_signer_key_verified': True,
        'idp_session_origin_authenticated': False,
        'mfa_challenge_verified': False,
        'one_time_challenge_consumed': False,
        'consent_source_authenticated': False,
        'independent_consent_record_committed': False,
        'provider_execution_admitted': False,
        'release_authorized': False,
    }
