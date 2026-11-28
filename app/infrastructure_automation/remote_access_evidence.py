"""Combined local access evidence review for future remote preflight (#5184/#5185).

No worker admission, provider access, credential material, network or SSH.
The caller owns the authenticated transaction, target and operation approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from app.extensions.db import db
from app.infrastructure_automation.credential_grants import (
    review_current_credential_grant,
    review_remote_credential_draft,
)
from app.infrastructure_automation.ssh_trust_lifecycle import review_current_console_trust
from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import canonical_statement
from app.models.scope_access import AutomationCredentialScopeTarget, ScopeAccessPolicy


@dataclass(frozen=True, slots=True, repr=False)
class RemoteAccessEvidence:
    """Correlation only; never a permit or material-delivery instruction."""

    fingerprint: str
    expires_at: datetime
    execution_authorized: bool = False


def review_remote_access_evidence(
    *, actor_user_id: int, connection_id: int, assignment_id: int, now: datetime
) -> RemoteAccessEvidence | None:
    """Require one active credential grant AND current independently verified host trust."""
    grant = review_current_credential_grant(
        actor_user_id=actor_user_id, connection_id=connection_id, assignment_id=assignment_id, now=now
    )
    if grant is None:
        return None
    draft = review_remote_credential_draft(
        actor_user_id=actor_user_id, connection_id=connection_id, assignment_id=assignment_id, now=now
    )
    if (
        draft is None
        or draft.execution_authorized is not False
        or draft.policy_id == grant.policy_id
        or draft.evidence != grant.evidence
    ):
        return None
    policy = db.session.get(ScopeAccessPolicy, grant.policy_id, populate_existing=True, with_for_update=True)
    target = db.session.get(
        AutomationCredentialScopeTarget, grant.policy_id, populate_existing=True, with_for_update=True
    )
    if (
        policy is None
        or target is None
        or policy.current_revision != grant.revision
        or target.ansible_connection_id != connection_id
        or target.assignment_id != assignment_id
    ):
        return None
    trust = review_current_console_trust(policy, target, now=now)
    if trust is None:
        return None
    expires_at = min(grant.expires_at, draft.expires_at, grant.evidence.expires_at, trust.expires_at)
    if expires_at <= now:
        return None
    fingerprint = sha256(
        canonical_statement({
            'schema': 'kaori.automation.remote_access_evidence.v2',
            'actor_id': actor_user_id,
            'connection_id': connection_id,
            'assignment_id': assignment_id,
            'policy_id': grant.policy_id,
            'policy_revision': grant.revision,
            'remote_draft_policy_id': draft.policy_id,
            'remote_draft_revision': draft.revision,
            'credential_evidence_ref': grant.evidence.evidence_ref,
            'host_revision': target.host_revision,
            'reference_fingerprint': target.reference_fingerprint,
            'trust_revision': trust.target.revision_number,
            'trust_evidence_ref': trust.evidence_ref,
            'expires_at': expires_at.isoformat(),
        })
    ).hexdigest()
    return RemoteAccessEvidence(fingerprint, expires_at)
