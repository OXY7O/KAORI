"""Bounded aggregate KV v2 version posture from committed source-owned evidence.

Never read Vault providers or Secret paths in normal Inventory rendering.
Historical, stale and incomplete observations cannot be current lifecycle facts.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import inspect, tuple_
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.providers.vault.kv2_inventory import (
    parse_approved_kv2_mounts,
)
from app.models.integration import IntegrationInstance
from app.models.secrets_pki import (
    SecretInventoryCollectionState,
    SecretProviderRepresentation,
    SecretVersionObservation,
)
from app.models.vault import VaultInstance
from app.secrets_pki.lifecycle import classify_kv2_version

_MAX_SOURCES = 25
_MAX_SCOPES = 200
_MAX_REPRESENTATIONS = 1500
_MAX_VERSIONS = 5000
_FRESHNESS = timedelta(hours=24)
_STATES = ('available', 'scheduled_deletion', 'soft_deleted', 'destroyed', 'unknown')


def _blocked(label: str, status: str = 'blocked') -> dict[str, Any]:
    """No numeric zero or source identity is exposed while evidence is missing."""
    return {
        'status': status,
        'label': label,
        'observed_versions': None,
        'available': None,
        'scheduled_deletion': None,
        'soft_deleted': None,
        'destroyed': None,
        'unknown': None,
        'coverage': 'Committed current-generation KV v2 version metadata only',
    }


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _schema_ready() -> bool:
    try:
        inspector = inspect(db.engine)
        required = {
            'vault_instances',
            'integration_instances',
            'secrets_pki_inventory_collection_states',
            'secrets_pki_secret_representations',
            'secrets_pki_secret_versions',
        }
        return required.issubset(set(inspector.get_table_names()))
    except SQLAlchemyError:
        return False


def build_kv2_version_posture(*, now: datetime | None = None) -> dict[str, Any]:
    """Evaluate only complete, fresh, currently approved source generations.

    This contract has no per-Secret identities, Vault paths or source names.
    An observed zero requires a complete committed scan. The source owner
    retains historical data, but this projection never counts historical
    not-observed representations or unrefreshed versions as current.
    """
    instant = _utc(now or datetime.now(UTC))
    if instant is None or not _schema_ready():
        return _blocked('Lifecycle Evidence Schema Not Ready')
    cutoff = instant - _FRESHNESS
    try:
        sources = (
            VaultInstance.query.join(VaultInstance.integration_instance)
            .filter(
                IntegrationInstance.integration_type == 'secrets_pki',
                IntegrationInstance.provider_key == 'vault',
                IntegrationInstance.enabled.is_(True),
                IntegrationInstance.lifecycle_status == 'active',
                IntegrationInstance.readiness_status == 'ready',
            )
            .order_by(VaultInstance.id.asc())
            .limit(_MAX_SOURCES + 1)
            .all()
        )
        if len(sources) > _MAX_SOURCES:
            return _blocked('Lifecycle Source Limit Exceeded')
        scopes = {
            (int(source.integration_instance_id), source.namespace or '', mount)
            for source in sources
            for mount in parse_approved_kv2_mounts(','.join(source.kv2_mounts or ()))
        }
        if not scopes:
            return _blocked('Approved KV v2 Source Required', 'not_configured')
        if len(scopes) > _MAX_SCOPES:
            return _blocked('Lifecycle Mount Scope Limit Exceeded')
        states = (
            SecretInventoryCollectionState.query.with_entities(
                SecretInventoryCollectionState.integration_instance_id,
                SecretInventoryCollectionState.provider_namespace,
                SecretInventoryCollectionState.mount,
                SecretInventoryCollectionState.status,
                SecretInventoryCollectionState.observed_count,
                SecretInventoryCollectionState.last_observed_at,
                SecretInventoryCollectionState.last_committed_at,
            )
            .filter(
                SecretInventoryCollectionState.integration_instance_id.in_(
                    [int(source.integration_instance_id) for source in sources]
                )
            )
            .limit(_MAX_SCOPES + 1)
            .all()
        )
        if len(states) > _MAX_SCOPES:
            return _blocked('Lifecycle Collection State Limit Exceeded')
        ready = {
            (row[0], row[1], row[2]): row
            for row in states
            if (row[0], row[1], row[2]) in scopes
            and row[3] == 'ready'
            and isinstance(row[4], int)
            and row[4] >= 0
            and (_utc(row[5]) or datetime.min.replace(tzinfo=UTC)) >= cutoff
            and (_utc(row[6]) or datetime.min.replace(tzinfo=UTC)) >= cutoff
            and (_utc(row[5]) or instant) <= instant
            and (_utc(row[6]) or instant) <= instant
        }
        if set(ready) != scopes:
            return _blocked('Lifecycle Evidence Incomplete or Stale', 'incomplete_evidence')
        records = (
            SecretProviderRepresentation.query.with_entities(
                SecretProviderRepresentation.id,
                SecretProviderRepresentation.integration_instance_id,
                SecretProviderRepresentation.provider_namespace,
                SecretProviderRepresentation.mount,
                SecretProviderRepresentation.last_observed_at,
            )
            .filter(
                tuple_(
                    SecretProviderRepresentation.integration_instance_id,
                    SecretProviderRepresentation.provider_namespace,
                    SecretProviderRepresentation.mount,
                ).in_(sorted(scopes)),
                SecretProviderRepresentation.observation_status == 'observed',
            )
            .limit(_MAX_REPRESENTATIONS + 1)
            .all()
        )
        if len(records) > _MAX_REPRESENTATIONS:
            return _blocked('Lifecycle Representation Limit Exceeded')
        counts = Counter((row[1], row[2], row[3]) for row in records)
        if any(counts.get(scope, 0) != ready[scope][4] for scope in scopes):
            return _blocked('Lifecycle Committed Count Conflict', 'incomplete_evidence')
        if not records:
            return {
                'status': 'observed_empty',
                'label': 'Qualified Committed Empty Inventory',
                'observed_versions': 0,
                **dict.fromkeys(_STATES, 0),
                'coverage': 'Committed current-generation KV v2 version metadata only',
            }
        generations = {row[0]: _utc(ready[(row[1], row[2], row[3])][5]) for row in records}
        if any(_utc(row[4]) != generations[row[0]] for row in records):
            return _blocked('Lifecycle Generation Mismatch', 'incomplete_evidence')
        versions = (
            SecretVersionObservation.query.with_entities(
                SecretVersionObservation.representation_id,
                SecretVersionObservation.destroyed,
                SecretVersionObservation.provider_deletion_time,
                SecretVersionObservation.last_observed_at,
            )
            .filter(SecretVersionObservation.representation_id.in_(list(generations)))
            .limit(_MAX_VERSIONS + 1)
            .all()
        )
        if len(versions) > _MAX_VERSIONS:
            return _blocked('Lifecycle Version Limit Exceeded')
        current_versions = [row for row in versions if _utc(row[3]) == generations.get(row[0])]
        observed_representation_ids = {row[0] for row in current_versions}
        if observed_representation_ids != set(generations):
            return _blocked('Lifecycle Version Coverage Incomplete', 'incomplete_evidence')
        posture = Counter(
            classify_kv2_version(
                destroyed=row[1],
                deletion_time=row[2],
                observed_at=generations[row[0]],
            )
            for row in current_versions
        )
        return {
            'status': 'ready',
            'label': 'Qualified Committed Version Posture',
            'observed_versions': len(current_versions),
            **{state: posture.get(state, 0) for state in _STATES},
            'coverage': 'Committed current-generation KV v2 version metadata only',
        }
    except (SQLAlchemyError, ValueError, TypeError, AttributeError):
        return _blocked('Lifecycle Evidence Unavailable')
