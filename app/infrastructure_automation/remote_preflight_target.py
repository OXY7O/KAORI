"""Exact three-host remote preflight target review (#5186).

Combines existing canonical inventory, grant and independent console evidence.
No source acceptance, image admission, secret retrieval or remote dispatch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256

from sqlalchemy import select

from app.extensions.db import db
from app.infrastructure_automation.host_registry import preview_inventory_intent
from app.infrastructure_automation.kubernetes.inventory_document import is_source_only_inventory_preparation
from app.infrastructure_automation.kubernetes.inventory_receipt import committed_inventory_receipt_review
from app.infrastructure_automation.kubernetes.source_policy import committed_source_state
from app.infrastructure_automation.remote_access_evidence import review_remote_access_evidence
from app.infrastructure_automation.remote_preflight_facts import RemoteFactsTarget
from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import canonical_statement
from app.models.automation import AutomationInventoryAssignment
from app.models.integration import IntegrationInstance

_EE = re.compile(r'sha256:[a-f0-9]{64}')


@dataclass(frozen=True, slots=True, repr=False)
class RemoteTargetReview:
    connection_id: int
    actor_id: int
    source_sha: str
    ee_digest: str
    inventory_fingerprint: str
    host_registry_fingerprint: str
    access_fingerprint: str
    targets: tuple[RemoteFactsTarget, ...]
    expires_at: datetime
    execution_authorized: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class SourceOnlyActivationIntent:
    """Redacted prerequisite identity; deliberately not a RemoteTargetReview."""

    connection_id: int
    actor_id: int
    source_sha: str
    ee_digest: str
    inventory_fingerprint: str
    host_registry_fingerprint: str
    access_fingerprint: str
    expires_at: datetime
    execution_authorized: bool = False


def review_remote_preflight_target(
    *, actor_id: int, connection_id: int, now: datetime
) -> RemoteTargetReview | None:
    """Return only qualified exact target evidence to existing review callers."""
    _, target = diagnose_remote_preflight_target(actor_id=actor_id, connection_id=connection_id, now=now)
    return target


def diagnose_remote_preflight_target(
    *, actor_id: int, connection_id: int, now: datetime, allow_source_only_diagnostics: bool = False
) -> tuple[str, RemoteTargetReview | None]:
    """Return a runtime review target only on the original enabled path."""
    state, evidence = _evaluate_remote_preflight_target(
        actor_id=actor_id, connection_id=connection_id, now=now,
        allow_source_only_diagnostics=allow_source_only_diagnostics,
    )
    return state, evidence if isinstance(evidence, RemoteTargetReview) else None


def review_source_only_activation_intent(
    *, actor_id: int, connection_id: int, now: datetime
) -> SourceOnlyActivationIntent | None:
    """Resolve only committed prerequisite identity inside the caller's transaction."""
    _, evidence = _evaluate_remote_preflight_target(
        actor_id=actor_id, connection_id=connection_id, now=now, allow_source_only_diagnostics=True,
    )
    return evidence if isinstance(evidence, SourceOnlyActivationIntent) else None


def _evaluate_remote_preflight_target(
    *, actor_id: int, connection_id: int, now: datetime, allow_source_only_diagnostics: bool
) -> tuple[str, RemoteTargetReview | SourceOnlyActivationIntent | None]:
    """Evaluate shared locked evidence without granting runtime or execution admission."""
    if (
        type(actor_id) is not int
        or actor_id <= 0
        or type(connection_id) is not int
        or connection_id <= 0
        or not isinstance(now, datetime)
        or now.utcoffset() is None
    ):
        return 'invalid_scope', None
    connection = db.session.get(IntegrationInstance, connection_id, populate_existing=True, with_for_update=True)
    if connection is None:
        return 'connection_unqualified', None
    source_only = allow_source_only_diagnostics is True and is_source_only_inventory_preparation(connection)
    if (
        (allow_source_only_diagnostics is True and not source_only)
        or (connection.enabled is not True and not source_only)
        or connection.integration_type != 'configuration_automation'
        or connection.provider_key != 'ansible'
        or connection.lifecycle_status != 'active'
    ):
        return 'connection_unqualified', None
    metadata = connection.metadata_json
    if not isinstance(metadata, dict) or committed_source_state(metadata) != 'checked':
        return 'source_not_checked', None
    source_sha, ee_digest = metadata.get('source_sha'), metadata.get('execution_environment_digest')
    if not isinstance(source_sha, str) or not isinstance(ee_digest, str) or _EE.fullmatch(ee_digest) is None:
        return 'ee_digest_unqualified', None
    assignments = list(db.session.execute(
        select(AutomationInventoryAssignment)
        .where(
            AutomationInventoryAssignment.integration_instance_id == connection_id,
            AutomationInventoryAssignment.enabled.is_(True),
        )
        .order_by(AutomationInventoryAssignment.id)
        .limit(4)
        .with_for_update(of=AutomationInventoryAssignment)
        .execution_options(populate_existing=True)
    ).scalars().all())
    if len(assignments) != 3 or any(assignment.host is None for assignment in assignments):
        return 'topology_unqualified', None
    for assignment in assignments:
        db.session.refresh(assignment.host, with_for_update=True)
    roles = [assignment.role for assignment in assignments]
    if roles.count('control_plane') != 1 or roles.count('worker') != 2:
        return 'topology_unqualified', None
    if len({assignment.host.address for assignment in assignments}) != 3:
        return 'topology_unqualified', None
    preview = preview_inventory_intent(connection, assignments)
    if preview.inventory_fingerprint is None or preview.host_count != 3:
        return 'host_registry_unqualified', None
    receipt = committed_inventory_receipt_review(connection)
    if receipt.state != 'historical_aligned' or not receipt.parser_verified or receipt.fingerprint is None:
        return 'inventory_receipt_unqualified', None
    members = []
    targets = []
    expiries = [now + timedelta(minutes=15)]
    for assignment in assignments:
        access = review_remote_access_evidence(
            actor_user_id=actor_id, connection_id=connection_id, assignment_id=assignment.id, now=now
        )
        if access is None or access.execution_authorized is not False or access.expires_at <= now:
            return 'access_review_unqualified', None
        members.append({'assignment_id': assignment.id, 'fingerprint': access.fingerprint})
        targets.append(RemoteFactsTarget(f'kaori-{assignment.id}', assignment.host_id, assignment.role))
        expiries.append(access.expires_at)
    schema = (
        'kaori.automation.source_only_activation_intent.v1'
        if source_only else 'kaori.automation.remote_preflight_target.v1'
    )
    fingerprint = sha256(canonical_statement({
        'schema': schema,
        'connection_id': connection_id,
        'actor_id': actor_id,
        'source_sha': source_sha,
        'execution_environment_digest': ee_digest,
        'inventory_fingerprint': receipt.fingerprint,
        'host_registry_fingerprint': preview.inventory_fingerprint,
        'members': members,
    })).hexdigest()
    if source_only:
        return 'runtime_activation_required', SourceOnlyActivationIntent(
            connection_id=connection_id,
            actor_id=actor_id,
            source_sha=source_sha,
            ee_digest=ee_digest,
            inventory_fingerprint=receipt.fingerprint,
            host_registry_fingerprint=preview.inventory_fingerprint,
            access_fingerprint=fingerprint,
            expires_at=min(expiries),
        )
    return 'historical_target_qualified', RemoteTargetReview(
        connection_id=connection_id,
        actor_id=actor_id,
        source_sha=source_sha,
        ee_digest=ee_digest,
        inventory_fingerprint=receipt.fingerprint,
        host_registry_fingerprint=preview.inventory_fingerprint,
        access_fingerprint=fingerprint,
        targets=tuple(targets),
        expires_at=min(expiries),
    )
