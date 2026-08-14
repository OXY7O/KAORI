from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from app.extensions.db import db
from app.knowledge.system_catalog import get_system_runbook, is_system_runbook_key
from app.knowledge.validation import validate_publication
from app.models.audit import AuditEvent
from app.models.knowledge import KnowledgeRunbook, KnowledgeRunbookRevision
from app.resolver.registry import ResolverRegistry

VIEW_PERMISSION = 'knowledge.runbooks.view'
MANAGE_PERMISSION = 'knowledge.runbooks.manage'
PUBLISH_PERMISSION = 'knowledge.runbooks.publish'


class KnowledgeError(ValueError):
    """Raised when a runbook lifecycle or integrity rule is violated."""


def custom_runbook_authoring_enabled(config: Mapping[str, Any]) -> bool:
    """Custom runbook authoring remains intentionally disabled until KAORI matures the authoring contract."""

    return bool(config.get('CUSTOM_RUNBOOK_AUTHORING_ENABLED', False))


def assert_custom_runbook_authoring_enabled(config: Mapping[str, Any]) -> None:
    if not custom_runbook_authoring_enabled(config):
        raise KnowledgeError(
            'Custom runbook authoring is not available yet. Use a validated KAORI System Runbook from the catalog.'
        )


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _require(permissions: Collection[str], permission: str) -> None:
    if permission not in permissions:
        raise KnowledgeError(f'Missing required permission: {permission}.')


def create_runbook(
    *,
    runbook_key: str,
    title: str,
    description: str | None,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
) -> KnowledgeRunbook:
    _require(actor_permissions, MANAGE_PERMISSION)
    key = runbook_key.strip()
    if not key or not title.strip():
        raise KnowledgeError('Runbook key and title are required.')
    existing = KnowledgeRunbook.query.filter_by(runbook_key=key).first()
    if existing is not None:
        return existing
    record = KnowledgeRunbook()
    record.runbook_key = key
    record.title = title.strip()
    record.description = description
    record.created_by_user_id = actor_user_id
    db.session.add(record)
    _audit(actor_user_id, key, 'knowledge.runbook.created', 'KAORI runbook created.', {'title': record.title})
    db.session.commit()
    return record


def create_revision(
    runbook: KnowledgeRunbook,
    *,
    version: str,
    action_key: str,
    resolver_key: str,
    approval_policy: str,
    required_evidence: Sequence[str],
    parameter_schema: Mapping[str, Any],
    steps: Sequence[Mapping[str, Any]],
    rollback: Mapping[str, Any] | None,
    required_capabilities: Sequence[str] = (),
    compatibility_profiles: Sequence[str] = (),
    change_level: str = 'patch',
    actor_user_id: int | None,
    actor_permissions: Collection[str],
) -> KnowledgeRunbookRevision:
    _require(actor_permissions, MANAGE_PERMISSION)
    if runbook.lifecycle_status != 'active':
        raise KnowledgeError('Only active runbooks can receive new revisions.')
    if approval_policy not in {'allowed', 'needs_approval', 'blocked'}:
        raise KnowledgeError('Unsupported runbook approval policy.')
    evidence = sorted({item.strip() for item in required_evidence if item.strip()})
    payload = {
        'runbook_key': runbook.runbook_key,
        'version': version.strip(),
        'action_key': action_key.strip(),
        'resolver_key': resolver_key.strip(),
        'approval_policy': approval_policy,
        'required_evidence': evidence,
        'required_capabilities': sorted({item.strip() for item in required_capabilities if item.strip()}),
        'compatibility_profiles': sorted({item.strip() for item in compatibility_profiles if item.strip()}),
        'change_level': change_level,
        'parameter_schema': dict(parameter_schema),
        'steps': [dict(step) for step in steps],
        'rollback': dict(rollback) if rollback else None,
    }
    if not payload['version'] or not payload['action_key'] or not payload['resolver_key'] or not payload['steps']:
        raise KnowledgeError('Version, action, resolver, and at least one runbook step are required.')
    revision = KnowledgeRunbookRevision()
    revision.runbook_id = runbook.id
    revision.version = payload['version']
    revision.publication_status = 'draft'
    revision.action_key = payload['action_key']
    revision.resolver_key = payload['resolver_key']
    revision.approval_policy = approval_policy
    revision.required_evidence_json = evidence
    revision.required_capabilities_json = payload['required_capabilities']
    revision.compatibility_profiles_json = payload['compatibility_profiles']
    revision.change_level = change_level
    revision.parameter_schema_json = payload['parameter_schema']
    revision.steps_json = payload['steps']
    revision.rollback_json = payload['rollback']
    revision.content_hash = _canonical_hash(payload)
    revision.created_by_user_id = actor_user_id
    db.session.add(revision)
    db.session.commit()
    return revision


def publish_revision(
    revision: KnowledgeRunbookRevision,
    *,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
    resolver_registry: ResolverRegistry,
    available_capabilities: Sequence[str] = (),
    compatibility_profile: str | None = None,
    now: datetime | None = None,
) -> KnowledgeRunbookRevision:
    _require(actor_permissions, PUBLISH_PERMISSION)
    if revision.publication_status != 'draft':
        raise KnowledgeError('Only draft runbook revisions can be published.')
    if revision.runbook.lifecycle_status != 'active':
        raise KnowledgeError('Runbook must be active before publication.')
    previous = (
        KnowledgeRunbookRevision.query.filter(
            KnowledgeRunbookRevision.runbook_id == revision.runbook_id,
            KnowledgeRunbookRevision.publication_status.in_(('published', 'withdrawn')),
            KnowledgeRunbookRevision.id != revision.id,
        )
        .order_by(KnowledgeRunbookRevision.published_at.desc(), KnowledgeRunbookRevision.id.desc())
        .first()
    )
    result = validate_publication(
        revision,
        resolver_registry=resolver_registry,
        available_capabilities=available_capabilities,
        compatibility_profile=compatibility_profile,
        previous_published_version=previous.version if previous is not None else None,
    )
    revision.publication_validation_json = result.as_dict()
    revision.reviewed_by_user_id = actor_user_id
    revision.reviewed_at = now or datetime.now(UTC)
    if not result.valid:
        db.session.flush()
        raise KnowledgeError('Runbook publication validation failed: ' + ' '.join(result.errors))
    revision.publication_status = 'published'
    revision.published_by_user_id = actor_user_id
    revision.published_at = now or datetime.now(UTC)
    _audit(
        actor_user_id,
        revision.public_id,
        'knowledge.runbook_revision.published',
        'KAORI runbook revision published.',
        {
            'runbook_key': revision.runbook.runbook_key,
            'version': revision.version,
            'content_hash': revision.content_hash,
        },
    )
    db.session.commit()
    return revision


def withdraw_revision(
    revision: KnowledgeRunbookRevision,
    *,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
    now: datetime | None = None,
) -> KnowledgeRunbookRevision:
    _require(actor_permissions, PUBLISH_PERMISSION)
    if revision.publication_status != 'published':
        raise KnowledgeError('Only published runbook revisions can be withdrawn.')
    revision.publication_status = 'withdrawn'
    revision.withdrawn_at = now or datetime.now(UTC)
    _audit(
        actor_user_id,
        revision.public_id,
        'knowledge.runbook_revision.withdrawn',
        'KAORI runbook revision withdrawn.',
        {'runbook_key': revision.runbook.runbook_key, 'version': revision.version},
    )
    db.session.commit()
    return revision


def activate_system_runbook(
    *,
    runbook_key: str,
    actor_user_id: int | None,
    actor_permissions: Collection[str],
    resolver_registry: ResolverRegistry,
) -> KnowledgeRunbookRevision:
    """Materialize and publish one source-controlled system runbook idempotently."""

    _require(actor_permissions, MANAGE_PERMISSION)
    _require(actor_permissions, PUBLISH_PERMISSION)
    definition = get_system_runbook(runbook_key)
    if definition is None:
        raise KnowledgeError('Unknown KAORI System Runbook catalog key.')

    descriptor = resolver_registry.describe(definition.action_key)
    runbook = KnowledgeRunbook.query.filter_by(runbook_key=definition.runbook_key).first()
    if runbook is None:
        runbook = create_runbook(
            runbook_key=definition.runbook_key,
            title=definition.title,
            description=definition.description,
            actor_user_id=actor_user_id,
            actor_permissions=actor_permissions,
        )
    elif runbook.lifecycle_status != 'active':
        raise KnowledgeError('System Runbook must be active before catalog activation.')

    # System identity metadata follows the source-controlled catalog. Executable content remains immutable per version.
    metadata_changed = runbook.title != definition.title or runbook.description != definition.description
    if metadata_changed:
        runbook.title = definition.title
        runbook.description = definition.description
        _audit(
            actor_user_id,
            definition.runbook_key,
            'knowledge.system_runbook.metadata_synchronized',
            'KAORI synchronized System Runbook catalog metadata.',
            {'version': definition.version},
        )
        db.session.commit()

    revision = KnowledgeRunbookRevision.query.filter_by(
        runbook_id=runbook.id,
        version=definition.version,
    ).one_or_none()
    if revision is not None:
        if revision.content_hash != definition.content_hash:
            raise KnowledgeError(
                'System Runbook catalog drift detected for this version. The stored immutable revision does not match '
                'the KAORI source-controlled contract.'
            )
        if revision.publication_status == 'published':
            return revision
        if revision.publication_status == 'withdrawn':
            raise KnowledgeError(
                'System Runbook revision was withdrawn and cannot be silently republished. Upgrade the catalog version '
                'or restore the database through the governed change path.'
            )
    else:
        revision = create_revision(
            runbook,
            version=definition.version,
            action_key=definition.action_key,
            resolver_key=definition.resolver_key,
            approval_policy=definition.approval_policy,
            required_evidence=definition.required_evidence,
            required_capabilities=definition.required_capabilities,
            compatibility_profiles=definition.compatibility_profiles,
            change_level=definition.change_level,
            parameter_schema=definition.parameter_schema,
            steps=definition.steps,
            rollback=definition.recovery,
            actor_user_id=actor_user_id,
            actor_permissions=actor_permissions,
        )

    compatibility_profile = (
        descriptor.compatibility_profiles[0] if len(descriptor.compatibility_profiles) == 1 else None
    )
    published = publish_revision(
        revision,
        actor_user_id=actor_user_id,
        actor_permissions=actor_permissions,
        resolver_registry=resolver_registry,
        available_capabilities=descriptor.capability_keys,
        compatibility_profile=compatibility_profile,
    )
    _audit(
        actor_user_id,
        published.public_id,
        'knowledge.system_runbook.activated',
        'KAORI System Runbook activated from the validated catalog.',
        {
            'runbook_key': definition.runbook_key,
            'version': definition.version,
            'content_hash': definition.content_hash,
        },
    )
    db.session.commit()
    return published


def assert_binding_uses_allowed_runbook(
    revision: KnowledgeRunbookRevision,
    *,
    config: Mapping[str, Any],
) -> None:
    if custom_runbook_authoring_enabled(config):
        return
    if not is_system_runbook_key(revision.runbook.runbook_key):
        raise KnowledgeError(
            'Custom runbook bindings are not available yet. Select a published KAORI System Runbook revision.'
        )


def assert_revision_mutation_allowed(
    revision: KnowledgeRunbookRevision,
    *,
    config: Mapping[str, Any],
    operation: str,
) -> None:
    if is_system_runbook_key(revision.runbook.runbook_key):
        raise KnowledgeError(
            f'System Runbook revisions are source-controlled and cannot be {operation} manually. '
            'Use the System Runbook Catalog and environment binding/policy controls instead.'
        )
    assert_custom_runbook_authoring_enabled(config)


def resolve_published_revision(*, runbook_key: str, version: str | None = None) -> KnowledgeRunbookRevision:
    query = KnowledgeRunbookRevision.query.join(KnowledgeRunbook).filter(
        KnowledgeRunbook.runbook_key == runbook_key,
        KnowledgeRunbook.lifecycle_status == 'active',
        KnowledgeRunbookRevision.publication_status == 'published',
    )
    if version is not None:
        query = query.filter(KnowledgeRunbookRevision.version == version)
    revision = query.order_by(KnowledgeRunbookRevision.published_at.desc(), KnowledgeRunbookRevision.id.desc()).first()
    if revision is None:
        raise KnowledgeError('No active published runbook revision matches the request.')
    return revision


def assert_required_evidence(revision: KnowledgeRunbookRevision, evidence: Mapping[str, Any]) -> None:
    missing = [key for key in revision.required_evidence_json if key not in evidence]
    if missing:
        raise KnowledgeError(f'Runbook evidence is incomplete: {", ".join(sorted(missing))}.')


def _audit(actor_user_id: int | None, target_id: str, action: str, summary: str, metadata: Mapping[str, Any]) -> None:
    event = AuditEvent()
    event.actor_user_id = actor_user_id
    event.action = action
    event.target_type = 'knowledge_runbook'
    event.target_id = target_id
    event.summary = summary
    event.metadata_json = dict(metadata)
    db.session.add(event)
