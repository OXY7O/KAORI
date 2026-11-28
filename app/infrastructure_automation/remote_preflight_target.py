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


def review_remote_preflight_target(
    *, actor_id: int, connection_id: int, now: datetime
) -> RemoteTargetReview | None:
    """Require current exact access evidence for all three canonical members.

    The internal caller owns the transaction and authenticated operation.
    The provider inventory receipt is historical, not a native currentness
    proof. A separate authorized worker must recheck before material access.
    """
    if (
        type(actor_id) is not int
        or actor_id <= 0
        or type(connection_id) is not int
        or connection_id <= 0
        or not isinstance(now, datetime)
        or now.utcoffset() is None
    ):
        return None
    connection = db.session.get(IntegrationInstance, connection_id, populate_existing=True, with_for_update=True)
    if connection is None or not connection.enabled:
        return None
    metadata = connection.metadata_json
    if not isinstance(metadata, dict) or committed_source_state(metadata) != 'checked':
        return None
    source_sha, ee_digest = metadata.get('source_sha'), metadata.get('execution_environment_digest')
    if not isinstance(source_sha, str) or not isinstance(ee_digest, str) or _EE.fullmatch(ee_digest) is None:
        return None
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
    if len(assignments) != 3:
        return None
    for assignment in assignments:
        db.session.refresh(assignment.host, with_for_update=True)
    roles = [assignment.role for assignment in assignments]
    if roles.count('control_plane') != 1 or roles.count('worker') != 2:
        return None
    if len({assignment.host.address for assignment in assignments}) != 3:
        return None
    preview = preview_inventory_intent(connection, assignments)
    receipt = committed_inventory_receipt_review(connection)
    if (
        preview.inventory_fingerprint is None
        or preview.host_count != 3
        or receipt.state != 'historical_aligned'
        or not receipt.parser_verified
        or receipt.fingerprint is None
    ):
        return None
    members = []
    targets = []
    expiries = [now + timedelta(minutes=15)]
    for assignment in assignments:
        access = review_remote_access_evidence(
            actor_user_id=actor_id, connection_id=connection_id, assignment_id=assignment.id, now=now
        )
        if access is None or access.expires_at <= now:
            return None
        members.append({'assignment_id': assignment.id, 'fingerprint': access.fingerprint})
        targets.append(RemoteFactsTarget(f'kaori-{assignment.id}', assignment.host_id, assignment.role))
        expiries.append(access.expires_at)
    fingerprint = sha256(canonical_statement({
        'schema': 'kaori.automation.remote_preflight_target.v1',
        'connection_id': connection_id,
        'actor_id': actor_id,
        'source_sha': source_sha,
        'execution_environment_digest': ee_digest,
        'inventory_fingerprint': receipt.fingerprint,
        'host_registry_fingerprint': preview.inventory_fingerprint,
        'members': members,
    })).hexdigest()
    return RemoteTargetReview(
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
