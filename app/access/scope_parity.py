"""Read-only scoped-access parity assessment for reviewed route cutover (#2726).

Never changes current RBAC route responses, seeds grants, or exposes source
identity. Structured diffs are internal operator evidence, not authorization.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.exc import SQLAlchemyError

from app.access.scope_policy import evaluate_exact_vault_scope
from app.extensions.db import db
from app.models.user import User

_MAX_SHADOW_SAMPLES = 200


@dataclass(frozen=True, slots=True, repr=False)
class ScopeParityFinding:
    baseline_allowed: bool
    scoped_decision: Literal['allow', 'deny', 'unavailable']
    variance: Literal[
        'parity_allowed',
        'parity_denied',
        'legacy_allowed_scope_denied',
        'legacy_denied_scope_allowed',
        'scoped_unavailable',
    ]

    @property
    def requires_review(self) -> bool:
        return self.variance not in {'parity_allowed', 'parity_denied'}


def compare_scope_parity(
    *,
    actor_user_id: int,
    instance_id: int,
    provider_namespace: str,
    mount: str,
) -> ScopeParityFinding:
    """Compare historical RBAC to proposed scoped admission without enforcement.

    Source/actor identifiers are never returned; errors do not grant access.
    Do not send per-user parity classifications to unauthorized UI consumers.
    """
    baseline = False
    if type(actor_user_id) is int and actor_user_id > 0:
        try:
            actor = db.session.get(User, actor_user_id)
            baseline = bool(actor is not None and actor.is_active and actor.has_permission('secrets_pki.view'))
        except (SQLAlchemyError, ValueError, TypeError, AttributeError):
            baseline = False

    result = evaluate_exact_vault_scope(
        actor_user_id=actor_user_id,
        instance_id=instance_id,
        provider_namespace=provider_namespace,
        mount=mount,
    )
    if result.status == 'unavailable':
        variance = 'scoped_unavailable'
    elif baseline and result.allowed:
        variance = 'parity_allowed'
    elif not baseline and not result.allowed:
        variance = 'parity_denied'
    elif baseline:
        variance = 'legacy_allowed_scope_denied'
    else:
        variance = 'legacy_denied_scope_allowed'
    return ScopeParityFinding(baseline, result.status, variance)


def summarize_scope_parity(
    findings: Sequence[ScopeParityFinding],
) -> dict[str, int | str]:
    """Aggregate bounded counts only: no role/user/source/Secret disclosure."""
    if len(findings) > _MAX_SHADOW_SAMPLES:
        raise ValueError('Scoped parity assessment exceeds approved sample bound.')
    counts = Counter(item.variance for item in findings)
    return {
        'mode': 'non_enforcing_shadow',
        'sample_count': len(findings),
        'parity_allowed': counts['parity_allowed'],
        'parity_denied': counts['parity_denied'],
        'legacy_allowed_scope_denied': counts['legacy_allowed_scope_denied'],
        'legacy_denied_scope_allowed': counts['legacy_denied_scope_allowed'],
        'scoped_unavailable': counts['scoped_unavailable'],
        'requires_review': sum(item.requires_review for item in findings),
        'cutover_admitted': 0,
    }
