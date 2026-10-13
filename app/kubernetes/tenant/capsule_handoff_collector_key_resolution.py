"""Source-disabled backend collector-key resolution for Capsule handoff #1229.

Broker and policy MUST eventually be independently registered server-side
(e.g. a reviewed Vault/KMS adapter and separately governed pin registry).
This file registers neither, reads no secrets, and does not contact Vault.
Never pass request-supplied broker, pin policy or key material as trust.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol

from app.kubernetes.tenant.capsule_handoff_collector_key_pin import (
    inspect_capsule_collector_key_pin,
)
from app.kubernetes.tenant.capsule_handoff_collector_receipt import (
    inspect_capsule_collector_receipt,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import _digest

# Both source constants must be changed by a separately authorized PR.
# Neither environment variables nor caller arguments override this hold.
_COLLECTOR_RESOLVER_ENABLED = False
_TRUSTED_COLLECTOR_INGRESS_ENABLED = False


class CapsuleCollectorKeyBroker(Protocol):
    """Privileged backend connector, NOT a user-controlled receipt or payload."""

    def read_key(
        self,
        *,
        cluster_id: str,
        collector_id: str,
        key_id: str,
    ) -> bytes: ...

    def read_pin(
        self,
        *,
        cluster_id: str,
        collector_id: str,
        key_id: str,
    ) -> Mapping[str, Any]: ...


class CapsuleCollectorPinPolicy(Protocol):
    """Independent operator-owned policy (not supplied by collector itself)."""

    def expected_fingerprint(
        self,
        *,
        cluster_id: str,
        collector_id: str,
        key_id: str,
    ) -> str: ...


def review_capsule_collector_via_broker_staged(
    *,
    resource_report: Mapping[str, Any],
    claims: list[Mapping[str, Any]],
    receipt: Mapping[str, Any],
    broker: CapsuleCollectorKeyBroker,
    operator_policy: CapsuleCollectorPinPolicy,
    expected_cluster_id: str,
    expected_collector_id: str,
    expected_key_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Unregistered, unreachable broker call; return digests, NEVER key bytes.

    Checking a pinned key and valid MAC cannot attest upstream apiserver
    events or controller origin. Raw key bytes cannot be securely zeroized
    in Python and therefore must not be logged, cached or returned.
    """
    if not _COLLECTOR_RESOLVER_ENABLED or not _TRUSTED_COLLECTOR_INGRESS_ENABLED:
        raise PermissionError(
            'Capsule collector key resolution remains source-disabled pending '
            'trusted ingress, key broker and operator gate approval.'
        )
    if (
        not isinstance(resource_report, Mapping)
        or not isinstance(receipt, Mapping)
        or not isinstance(claims, list)
        or not all(
            isinstance(x, str) and x
            for x in (
                expected_cluster_id,
                expected_collector_id,
                expected_key_id,
            )
        )
        or resource_report.get('cluster_id') != expected_cluster_id
        or receipt.get('cluster_id') != expected_cluster_id
        or receipt.get('collector_id') != expected_collector_id
        or receipt.get('key_id') != expected_key_id
    ):
        raise ValueError('Capsule broker resolution requires exact server-selected collector scope.')
    instant = datetime.now(UTC) if now is None else now
    if not isinstance(instant, datetime) or instant.tzinfo is None:
        raise ValueError('Capsule collector resolution requires timezone-aware current time.')
    # The future integration must construct both dependencies from a
    # trusted server-side registry, not from request body or client headers.
    key: bytes | None = None
    try:
        pin = broker.read_pin(
            cluster_id=expected_cluster_id,
            collector_id=expected_collector_id,
            key_id=expected_key_id,
        )
        expected_fingerprint = operator_policy.expected_fingerprint(
            cluster_id=expected_cluster_id,
            collector_id=expected_collector_id,
            key_id=expected_key_id,
        )
        key = broker.read_key(
            cluster_id=expected_cluster_id,
            collector_id=expected_collector_id,
            key_id=expected_key_id,
        )
        matched = inspect_capsule_collector_key_pin(
            descriptor=pin,
            cluster_id=expected_cluster_id,
            collector_id=expected_collector_id,
            key_id=expected_key_id,
            backend_key_material=key,
            pinned_fingerprint_sha256=expected_fingerprint,
            now=instant,
        )
        reviewed = inspect_capsule_collector_receipt(
            resource_report=resource_report,
            claims=claims,
            receipt=receipt,
            trusted_collector_id=expected_collector_id,
            trusted_key_id=expected_key_id,
            trusted_hmac_key=key,
            now=instant,
        )
    except Exception:
        # Do not surface exceptions from a future secret broker, including
        # key paths, tokens or upstream service response bodies.
        raise ValueError('Capsule collector key or audit receipt could not be verified.') from None
    finally:
        key = None
    if matched.get('key_material_matches_pin') is not True or reviewed.get('collector_mac_verified') is not True:
        raise ValueError('Capsule collector pin and receipt validation disagreed.')
    return {
        'status': 'backend_broker_pin_and_collector_mac_correlated_unadmitted',
        'tenant_id': resource_report['tenant_id'],
        'cluster_id': expected_cluster_id,
        'plan_sha256': resource_report['plan_sha256'],
        'worklist_sha256': resource_report['worklist_sha256'],
        'resource_review_sha256': resource_report['resource_review_sha256'],
        'pin_record_sha256': matched['pin_record_sha256'],
        'collector_receipt_sha256': reviewed['collector_receipt_sha256'],
        'key_scope_sha256': _digest(
            {
                'cluster_id': expected_cluster_id,
                'collector_id': expected_collector_id,
                'key_id': expected_key_id,
            }
        ),
        'key_material_matches_pin': True,
        'collector_mac_verified': True,
        'server_broker_registration_verified': False,
        'operator_policy_origin_attested': False,
        'trusted_ingress_implemented': False,
        'apiserver_audit_integrity_verified': False,
        'controller_origin_attested': False,
        'provider_execution_admitted': False,
        'auto_retry_authorized': False,
        'release_authorized': False,
        'secret_material_persisted': False,
    }
