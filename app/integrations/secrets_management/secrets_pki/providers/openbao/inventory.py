"""Local metadata observation for registered OpenBao; no material operations."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.commit_inventory import KV2CommitSummary, commit_local_openbao_inventory
from app.integrations.secrets_management.secrets_pki.providers.kv2_http import KV2HTTPTransport, SecretProviderError
from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import collect_kv2_metadata_with_token
from app.integrations.secrets_management.secrets_pki.providers.openbao.client import OpenBaoClient, _read_metadata, _verify_inspection_authority
from app.integrations.secrets_management.secrets_pki.providers.openbao.inventory_scope import (
    LocalOpenBaoInventoryScope,
    require_local_inventory_source,
    resolve_local_inventory_scope,
)
from app.integrations.secrets_management.secrets_pki.providers.openbao.qualification import _require_current_cluster
from app.models.integration import IntegrationInstance
from app.models.secrets_pki import SecretInventoryCollectionState


def _require_mount(transport: KV2HTTPTransport, scope: LocalOpenBaoInventoryScope, token: str) -> None:
    entry = _read_metadata(transport, token, '/v1/sys/mounts').get(scope.mount + '/')
    if (
        not isinstance(entry, dict) or entry.get('type') != 'kv'
        or not isinstance(entry.get('options'), dict) or entry['options'].get('version') != '2'
    ):
        raise SecretProviderError('The exact approved KV v2 mount was not observed.')


def _qualify(transport: KV2HTTPTransport, scope: LocalOpenBaoInventoryScope, token: str) -> None:
    _require_current_cluster(transport, cluster_id=scope.cluster_id)
    _verify_inspection_authority(transport, token, max_ttl=3600)
    _require_mount(transport, scope, token)


def _mark_failed(scope: LocalOpenBaoInventoryScope, started: datetime) -> None:
    try:
        identity = db.session.get(IntegrationInstance, scope.instance_id, populate_existing=True, with_for_update=True)
        require_local_inventory_source(scope, identity=identity, lock=True)
        state = SecretInventoryCollectionState.query.filter_by(
            integration_instance_id=scope.instance_id, provider_namespace='', mount=scope.mount
        ).with_for_update().one_or_none()
        if state is None:
            state = SecretInventoryCollectionState(
                integration_instance_id=scope.instance_id, provider_namespace='', mount=scope.mount
            )
            db.session.add(state)
        elif state.last_observed_at is not None:
            at = state.last_observed_at
            if (at if at.tzinfo is not None else at.replace(tzinfo=UTC)) >= started:
                db.session.rollback()
                return
        state.status = 'stale' if state.last_committed_at else 'failed'
        state.last_error = 'Local OpenBao metadata collection failed; previous evidence retained.'
        db.session.commit()
    except (ValueError, SQLAlchemyError):
        db.session.rollback()


def collect_local_inventory(scope: LocalOpenBaoInventoryScope, *, token: str) -> KV2CommitSummary:
    if (
        not isinstance(token, str) or not 1 <= len(token) <= 4096 or not token.isascii()
        or any(not 33 <= ord(char) <= 126 for char in token)
        or not os.getenv(OpenBaoClient.ca_bundle_env, '').strip()
    ):
        raise SecretProviderError('Scoped token and explicit OpenBao CA required.')
    if resolve_local_inventory_scope(scope.instance_id, scope.mount) != scope:
        raise SecretProviderError('OpenBao source changed.')
    db.session.rollback()
    transport = KV2HTTPTransport(
        endpoint=scope.endpoint, provider_label=OpenBaoClient.provider_label,
        allowed_origins_env=OpenBaoClient.allowed_origins_env, ca_bundle_env=OpenBaoClient.ca_bundle_env,
    )
    if transport.endpoint != scope.endpoint:
        raise SecretProviderError('Canonical OpenBao endpoint required.')
    started = datetime.now(UTC)
    try:
        _qualify(transport, scope, token)
        evidence = collect_kv2_metadata_with_token(transport, mount=scope.mount, token=token)
        _qualify(transport, scope, token)
        return commit_local_openbao_inventory(scope, evidence)
    except Exception:
        db.session.rollback()
        _mark_failed(scope, started)
        raise


def local_inventory_summary(instance_id: int) -> dict[str, object]:
    result: dict[str, object] = {'status': 'not_collected', 'observed_count': None, 'last_committed_at': None}
    try:
        mount = os.getenv('KAORI_LOCAL_OPENBAO_INVENTORY_MOUNT', '')
        resolve_local_inventory_scope(instance_id, mount)
        state = SecretInventoryCollectionState.query.filter_by(
            integration_instance_id=instance_id, provider_namespace='', mount=mount
        ).one_or_none()
        if state is not None:
            result.update(status=state.status, observed_count=state.observed_count, last_committed_at=state.last_committed_at)
    except (ValueError, SQLAlchemyError):
        db.session.rollback()
        result['status'] = 'scope_unavailable'
    return result
