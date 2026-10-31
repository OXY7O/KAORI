"""Exact-policy, read-only HTTP gateway for committed KV v2 Secret metadata.

Never accept Vault namespace or mount from the request. The existing
#724 policy evaluator and scoped_registry reader own sensitive access.
"""

from __future__ import annotations

from uuid import UUID

from flask import abort, render_template, request
from flask.typing import ResponseReturnValue
from flask_login import current_user
from app.secrets_pki.scoped_registry import read_governed_scoped_secret_registry, resolve_scoped_registry_mount

_MAX_PAGE = 40  # The committed scope itself caps at 200, with pages of five.


def _canonical_positive(raw: str) -> int | None:
    if (
        not isinstance(raw, str)
        or not raw
        or not raw.isascii()
        or not raw.isdecimal()
        or raw.startswith('0')
        or len(raw) > 10
    ):
        return None
    number = int(raw)
    return number if number > 0 and str(number) == raw else None


def _canonical_uuid(raw: str) -> str | None:
    if not isinstance(raw, str) or len(raw) != 36:
        return None
    try:
        normalized = str(UUID(raw))
    except (ValueError, TypeError, AttributeError):
        return None
    return normalized if raw == normalized else None


def _resolve_scope(*, actor_id: int, instance_id: int, policy_ref: str) -> tuple[str, str] | None:
    """Delegate exact-policy lookup without introducing a second grant path."""
    return resolve_scoped_registry_mount(actor_id=actor_id, instance_id=instance_id, policy_ref=policy_ref)


def scoped_registry_response() -> ResponseReturnValue:
    """Dedicated read-only scoped registry. No fleet fallback or Secret detail."""
    instance_raw = request.args.get('instance_id', '')
    policy_raw = request.args.get('scope_ref', '')
    if not instance_raw and not policy_raw:
        return render_template(
            'secrets_pki/scoped_registry.html',
            instance_id=None,
            scope_ref=None,
            registry=None,
        )
    instance_id = _canonical_positive(instance_raw)
    scope_ref = _canonical_uuid(policy_raw)
    page = _canonical_positive(request.args.get('page', '1'))
    if instance_id is None or scope_ref is None or page is None or page > _MAX_PAGE:
        abort(404)
    actor_id = getattr(current_user, 'id', None)
    if type(actor_id) is not int or actor_id < 1:
        abort(404)
    internal_scope = _resolve_scope(
        actor_id=actor_id,
        instance_id=instance_id,
        policy_ref=scope_ref,
    )
    if internal_scope is None:
        abort(404)

    result = read_governed_scoped_secret_registry(
        actor_id=actor_id,
        instance_id=instance_id,
        provider_namespace=internal_scope[0],
        mount=internal_scope[1],
        page=page,
        per_page=5,
    )
    if result.status == 'scope_required':
        abort(404)  # Same result for unknown, revoked or foreign resource.
    # Only opaque IDs and allowlisted safe row properties reach the template.
    return render_template(
        'secrets_pki/scoped_registry.html',
        instance_id=instance_id,
        scope_ref=scope_ref,
        registry=result,
    )
