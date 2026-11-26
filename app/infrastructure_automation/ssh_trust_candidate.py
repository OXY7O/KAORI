"""Non-authorizing host trust revision shape qualification (#5185).

The caller must resolve the latest revision and current access binding from
canonical committed state. This helper cannot establish independent console
provenance, verifier authorization, credential use or execution.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.infrastructure_automation.host_enrollment import host_revision
from app.infrastructure_automation.ssh_host_key import qualify_ed25519_host_key
from app.models.automation import (
    AutomationHostAccessBinding,
    AutomationHostTrustRevision,
    AutomationInventoryAssignment,
)

_EVIDENCE_DIGEST = re.compile(r'sha256:[a-f0-9]{64}')


def _utc(value: datetime) -> datetime:
    # Follow the existing SQLite/PostgreSQL committed timestamp convention.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _current_window(revision: AutomationHostTrustRevision, now: datetime) -> bool:
    return (
        now.utcoffset() is not None
        and revision.verified_at is not None
        and _utc(revision.verified_at) <= _utc(revision.recorded_at) <= now < _utc(revision.effective_until)
    )


def _independent_record(revision: AutomationHostTrustRevision, binding: AutomationHostAccessBinding) -> bool:
    return (
        revision.source_kind == 'independent_console'
        and _EVIDENCE_DIGEST.fullmatch(revision.evidence_ref) is not None
        and revision.requested_by_user_id > 0
        and revision.verified_by_user_id is not None
        and revision.verified_by_user_id > 0
        and revision.verified_by_user_id != revision.requested_by_user_id
        and revision.verified_by_user_id != binding.recorded_by_user_id
        and revision.recorded_by_user_id == revision.verified_by_user_id
    )


def trust_revision_candidate_matches(
    *,
    latest: AutomationHostTrustRevision | None,
    assignment: AutomationInventoryAssignment,
    binding: AutomationHostAccessBinding | None,
    now: datetime,
) -> bool:
    """Match only the latest candidate's shape; never return verified trust.

    A caller may not substitute an older active row for a revoked, expired
    or draft latest revision. Full source, provider, audit and independent
    console provenance qualification remain separate mandatory boundaries.
    """
    if latest is None or binding is None:
        return False
    if (
        latest.lifecycle_status != 'active'
        or latest.revision_number <= 0
        or assignment.enabled is not True
        or latest.assignment_id != assignment.id
        or binding.assignment_id != assignment.id
        or assignment.host.lifecycle_status != 'registered'
        or latest.host_revision != binding.host_revision
        or binding.host_revision != host_revision(assignment)
        or latest.reference_fingerprint != binding.reference_fingerprint
        or latest.address != assignment.host.address
        or latest.ssh_port != assignment.host.ssh_port
        or latest.host_key_digest != binding.host_key_digest
        or latest.algorithm != 'ssh-ed25519'
    ):
        return False
    if not _current_window(latest, now) or not _independent_record(latest, binding):
        return False
    return qualify_ed25519_host_key(latest.public_key, expected_digest=binding.host_key_digest) is not None
