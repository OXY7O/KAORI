"""Atomic KV v2 metadata reconciliation into provider-neutral Secret evidence.

Only admitted inventory workers may invoke this service. It does not expose
an HTTP route, dispatch its own Celery task, or store provider responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.providers.vault.kv2_inventory import (
    KV2CollectionEvidence,
    parse_approved_kv2_mounts,
)
from app.models.integration import IntegrationInstance
from app.models.secrets_pki import (
    SecretIdentity,
    SecretInventoryCollectionState,
    SecretProviderRepresentation,
    SecretVersionObservation,
)
from app.models.vault import VaultInstance


@dataclass(frozen=True, slots=True)
class KV2CommitSummary:
    integration_instance_id: int
    observed_secret_count: int
    observed_version_count: int
    not_observed_count: int
    committed_at: datetime


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def commit_kv2_inventory(
    integration_instance_id: int,
    evidence: KV2CollectionEvidence,
) -> KV2CommitSummary:
    """Commit one complete, bounded mount scan; never infer provider deletion.

    The *caller* is responsible for canonical JobExecution admission, scoped
    authorization, and provider access. This function enforces a second source
    eligibility boundary, a per-mount database lock and all-or-nothing commit.
    """
    if not evidence.complete:
        raise ValueError('Incomplete KV v2 evidence cannot be committed.')
    if evidence.observed_at.tzinfo is None:
        raise ValueError('KV v2 observed time must be timezone-aware.')
    if not evidence.mount or len(evidence.mount) > 160:
        raise ValueError('KV v2 mount is invalid for committed inventory.')
    if len(evidence.records) > 200:
        raise ValueError('KV v2 inventory exceeds the commit bound.')
    if len({row.path for row in evidence.records}) != len(evidence.records):
        raise ValueError('KV v2 metadata contains duplicate path identities.')

    # Serialize provider configuration admission with concurrent Vault edits:
    # integration identity is locked before provider row, then mount state.
    # An approved mount revoked while the worker was reading cannot be
    # committed under a stale pre-collection authorization decision.
    try:
        identity = db.session.execute(
            select(IntegrationInstance).where(IntegrationInstance.id == integration_instance_id).with_for_update()
        ).scalar_one_or_none()
        instance = db.session.execute(
            select(VaultInstance)
            .where(VaultInstance.integration_instance_id == integration_instance_id)
            .with_for_update(of=VaultInstance)
        ).scalar_one_or_none()
        if (
            identity is None
            or instance is None
            or identity.integration_type != 'secrets_pki'
            or identity.provider_key != 'vault'
            or identity.lifecycle_status != 'active'
            or not identity.enabled
            or identity.readiness_status != 'ready'
            or evidence.mount not in parse_approved_kv2_mounts(','.join(instance.kv2_mounts or ()))
        ):
            raise ValueError('The Vault provider and metadata mount are not eligible for committed reconciliation.')

        namespace = instance.namespace or ''
        if len(namespace) > 255 or any(len(row.path) > 1024 or row.mount != evidence.mount for row in evidence.records):
            raise ValueError('KV v2 representation scope exceeds supported bounds.')

        state = SecretInventoryCollectionState.query.filter_by(
            integration_instance_id=integration_instance_id,
            provider_namespace=namespace,
            mount=evidence.mount,
        ).first()
        if state is None:
            state = SecretInventoryCollectionState(
                integration_instance_id=integration_instance_id,
                provider_namespace=namespace,
                mount=evidence.mount,
                status='not_collected',
            )
            db.session.add(state)
            db.session.flush()

        db.session.execute(
            select(SecretInventoryCollectionState.id)
            .where(SecretInventoryCollectionState.id == state.id)
            .with_for_update()
        ).scalar_one()

        if state.last_observed_at is not None and evidence.observed_at <= _aware(state.last_observed_at):
            raise ValueError('KV v2 evidence is older than the existing committed generation.')

        existing_rows = (
            SecretProviderRepresentation.query.options(
                selectinload(SecretProviderRepresentation.versions),
            )
            .filter_by(
                integration_instance_id=integration_instance_id,
                provider_namespace=namespace,
                mount=evidence.mount,
            )
            .all()
        )
        existing = {row.path: row for row in existing_rows}
        digests = {row.path_sha256: row.path for row in existing_rows}
        if existing_rows and not evidence.records:
            raise ValueError('An unexpectedly empty KV v2 collection cannot replace prior committed evidence.')

        versions_count = 0
        for record in evidence.records:
            path_fingerprint = sha256(record.path.encode('utf-8')).hexdigest()
            conflicting_path = digests.get(path_fingerprint)
            if conflicting_path is not None and conflicting_path != record.path:
                raise ValueError('Conflicting Vault path identity evidence.')
            digests[path_fingerprint] = record.path
            representation = existing.pop(record.path, None)
            if representation is None:
                representation = SecretProviderRepresentation(
                    secret_identity=SecretIdentity(lifecycle_status='discovered'),
                    integration_instance_id=integration_instance_id,
                    provider_key='vault',
                    provider_namespace=namespace,
                    mount=evidence.mount,
                    path=record.path,
                    path_sha256=path_fingerprint,
                    representation_role='material_authority',
                )
                db.session.add(representation)
            if representation.current_version > record.current_version:
                raise ValueError('KV v2 current version regressed; source identity requires review.')
            representation.observation_status = 'observed'
            representation.current_version = record.current_version
            representation.oldest_version = record.oldest_version
            representation.max_versions = record.max_versions
            representation.cas_required = record.cas_required
            representation.last_observed_at = evidence.observed_at

            known_versions = {row.version: row for row in representation.versions}
            for observed_version in record.versions:
                version = known_versions.get(observed_version.version)
                if version is None:
                    version = SecretVersionObservation(version=observed_version.version)
                    representation.versions.append(version)
                elif version.destroyed and not observed_version.destroyed:
                    raise ValueError('KV v2 destroyed-version evidence cannot reverse.')
                version.provider_created_time = observed_version.created_time
                version.provider_deletion_time = observed_version.deletion_time
                version.destroyed = observed_version.destroyed
                version.last_observed_at = evidence.observed_at
                versions_count += 1

        # Absence from a successful complete scan is not proof of deletion,
        # revocation, compromise or material retirement. Preserve history.
        for missing in existing.values():
            missing.observation_status = 'not_observed'

        committed = datetime.now(UTC)
        state.status = 'ready'
        state.observed_count = len(evidence.records)
        state.last_observed_at = evidence.observed_at
        state.last_committed_at = committed
        state.last_error = None
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return KV2CommitSummary(
        integration_instance_id=integration_instance_id,
        observed_secret_count=len(evidence.records),
        observed_version_count=versions_count,
        not_observed_count=len(existing),
        committed_at=committed,
    )


def mark_kv2_inventory_failed(integration_instance_id: int, mount: str) -> None:
    """Persist a sanitized, scope-specific failure without erasing the last commit."""
    try:
        instance = VaultInstance.query.filter_by(integration_instance_id=integration_instance_id).first()
        if instance is None or mount not in parse_approved_kv2_mounts(','.join(instance.kv2_mounts or ())):
            return
        state = SecretInventoryCollectionState.query.filter_by(
            integration_instance_id=integration_instance_id,
            provider_namespace=instance.namespace or '',
            mount=mount,
        ).first()
        if state is None:
            state = SecretInventoryCollectionState(
                integration_instance_id=integration_instance_id,
                provider_namespace=instance.namespace or '',
                mount=mount,
            )
            db.session.add(state)
        state.status = 'stale' if state.last_committed_at else 'failed'
        state.last_error = 'Provider KV v2 metadata collection failed; previous committed evidence retained.'
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Never hide original collection failure with diagnostics containing Vault data.
