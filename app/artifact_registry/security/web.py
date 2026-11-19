"""Read-only Registry Security workspace rendering, without dispatch or RBAC decisions."""

from __future__ import annotations

from flask import render_template, request
from flask.typing import ResponseReturnValue

from app.artifact_registry.route_scope import _security_source_id
from app.artifact_registry.security.presentation import build_security


def _security_response(kind: str) -> ResponseReturnValue:
    context = build_security(
        kind=kind,
        section=request.args.get('section', '', type=str),
        search=request.args.get('q', '', type=str),
        severity=request.args.get('severity', '', type=str),
        provider=request.args.get('provider', '', type=str),
        source_id=_security_source_id(),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    template = (
        'artifact_registry/partials/_security_workspace.html'
        if request.headers.get('HX-Request') == 'true'
        else 'artifact_registry/security.html'
    )
    return render_template(template, security=context)


def _security_sync_context(kind: str) -> dict[str, object]:
    return build_security(
        kind=kind,
        section=request.form.get('section', '', type=str),
        search=request.form.get('q', '', type=str),
        severity=request.form.get('severity', '', type=str),
        provider=request.form.get('provider', '', type=str),
        source_id=_security_source_id(from_form=True),
        page=request.form.get('page', 1, type=int) or 1,
        per_page=request.form.get('per_page', 5, type=int) or 5,
    )
