"""Read-only ESO status qualification; candidate evidence, never Vault delivery."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from app.kubernetes.governance.tls_certificates.controller_evidence import validate_committed_controller_owners

_FRESHNESS = timedelta(hours=24)
Status = Literal['unknown', 'not_ready', 'reconciled_candidate']


@dataclass(frozen=True, slots=True, repr=False)
class ESOReadback:
    """Internal only: scope and UID must never appear in aggregate UI/logs."""

    cluster_id: str
    namespace: str
    controller_uid: str
    generation: int
    ready: bool
    refreshed_at: datetime
    observed_at: datetime


@dataclass(frozen=True, slots=True, repr=False)
class ESOTargetEvidence:
    """Immutable current TLS target evidence; hide identity from repr/logs."""

    target_cluster_id: str
    target_namespace: str
    target_secret_uid: str | None
    current_secret_uid: str | None
    target_fingerprint_sha256: str | None
    target_owner_refs: object
    target_observed_at: datetime
    current_identity_observed_at: datetime | None


@dataclass(frozen=True, slots=True)
class ESOAssessment:
    status: Status
    controller_reconciliation_observed: bool = False
    immutable_target_correlated: bool = False
    vault_to_controller_proven: bool = False
    delivery_proven: bool = False
    endpoint_serving_verified: bool = False


def _uid(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        return None
    return parsed if parsed == value else None


def _time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        item = value
    elif isinstance(value, str) and len(value) <= 48:
        try:
            item = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    else:
        return None
    return item.astimezone(UTC) if item.tzinfo is not None and item.utcoffset() is not None else None


def _generation(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 1 <= value <= 2**31 - 1 else None


def _scope(value: object) -> str | None:
    return value if isinstance(value, str) and 0 < len(value) <= 255 and value == value.strip() else None


def _recent(value: datetime, *, now: datetime) -> bool:
    return timedelta(0) <= now - value <= _FRESHNESS


def normalize_eso_readback(
    resource: object,
    *,
    cluster_id: str,
    observed_at: datetime,
) -> ESOReadback | None:
    """Normalize only typed ExternalSecret identity and coherent Ready status.

    ESO status ordinarily contains refreshTime, syncedResourceVersion and
    conditions rather than observedGeneration. A bounded sync marker admits
    status-only candidates; it cannot prove current spec generation or target
    Secret delivery. If optional generation is present it must be coherent.
    """
    observation = _time(observed_at)
    if not isinstance(resource, Mapping) or not _scope(cluster_id) or observation is None:
        return None
    metadata, status = resource.get('metadata'), resource.get('status')
    if (
        resource.get('kind') != 'ExternalSecret'
        or resource.get('apiVersion') not in {'external-secrets.io/v1', 'external-secrets.io/v1beta1'}
        or not isinstance(metadata, Mapping)
        or not isinstance(status, Mapping)
    ):
        return None
    uid = _uid(metadata.get('uid'))
    namespace = _scope(metadata.get('namespace'))
    generation = _generation(metadata.get('generation'))
    refreshed = _time(status.get('refreshTime'))
    conditions = status.get('conditions')
    observed_generation = status.get('observedGeneration')
    synced_version = status.get('syncedResourceVersion')
    if (
        uid is None
        or namespace is None
        or generation is None
        or (observed_generation is not None and _generation(observed_generation) != generation)
        or not isinstance(synced_version, str)
        or not 0 < len(synced_version) <= 128
        or synced_version != synced_version.strip()
        or refreshed is None
        or refreshed > observation
        or not isinstance(conditions, list)
        or not 1 <= len(conditions) <= 16
    ):
        return None
    ready = [item for item in conditions if isinstance(item, Mapping) and item.get('type') == 'Ready']
    if len(ready) != 1 or ready[0].get('status') not in {'True', 'False'}:
        return None
    condition_generation = ready[0].get('observedGeneration')
    if condition_generation is not None and _generation(condition_generation) != generation:
        return None
    return ESOReadback(
        cluster_id,
        namespace,
        uid,
        generation,
        ready[0]['status'] == 'True',
        refreshed,
        observation,
    )


def qualify_eso_reconciliation(
    receipt: ESOReadback | None,
    *,
    target: ESOTargetEvidence,
    controller_source_state: str,
    tls_source_state: str,
    now: datetime,
) -> ESOAssessment:
    """Exact owner/Secret UIDs plus independent fresh current UID: candidate only.

    ESO does not expose immutable target Secret UID, nor does Ready identify
    the Vault source. A caller must supply an independent Kubernetes UID
    readback; absence cannot silently become proof of materialization.
    """
    if not isinstance(target, ESOTargetEvidence):
        return ESOAssessment('unknown')
    instant, target_time, identity_time = (
        _time(now),
        _time(target.target_observed_at),
        _time(target.current_identity_observed_at),
    )
    if (
        instant is None
        or receipt is None
        or target_time is None
        or identity_time is None
        or controller_source_state != 'ready'
        or tls_source_state != 'ready'
        or receipt.cluster_id != target.target_cluster_id
        or receipt.namespace != target.target_namespace
        or not _scope(target.target_cluster_id)
        or not _scope(target.target_namespace)
        or not all(
            _recent(item, now=instant)
            for item in (
                receipt.observed_at,
                receipt.refreshed_at,
                target_time,
                identity_time,
            )
        )
        or target_time < receipt.refreshed_at
        or identity_time < target_time
    ):
        return ESOAssessment('unknown')
    uid, current_uid = _uid(target.target_secret_uid), _uid(target.current_secret_uid)
    fingerprint = target.target_fingerprint_sha256
    if (
        uid is None
        or uid != current_uid
        or not isinstance(fingerprint, str)
        or len(fingerprint) != 64
        or any(char not in '0123456789abcdef' for char in fingerprint)
    ):
        return ESOAssessment('unknown')
    owners = validate_committed_controller_owners(target.target_owner_refs)
    if owners != [{'kind': 'ExternalSecret', 'api_group': 'external-secrets.io', 'uid': receipt.controller_uid}]:
        return ESOAssessment('unknown')
    if not receipt.ready:
        return ESOAssessment('not_ready', immutable_target_correlated=True)
    return ESOAssessment(
        'reconciled_candidate',
        controller_reconciliation_observed=True,
        immutable_target_correlated=True,
    )
