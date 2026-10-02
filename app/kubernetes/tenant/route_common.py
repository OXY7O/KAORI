from __future__ import annotations

from typing import Any

from flask import Blueprint, g, make_response, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

from app.kubernetes.tenant.access_service import get_tenant_access_context
from app.kubernetes.tenant.admin_workspace import (
    get_access_grant_registry_context,
    get_credential_registry_context,
    get_group_registry_context,
    get_membership_registry_context,
    get_namespace_access_registry_context,
    get_tenant_summary_context,
)
from app.kubernetes.tenant.discovery_service import get_tenant_discovery_context
from app.kubernetes.tenant.service import get_tenant_context, get_tenant_registry_context
from app.kubernetes.tenant.workspace import get_tenant_sync_workspace_context, get_tenant_workspace_context
from app.platform_operations.notifications.service import record_operational_activity


tenant_bp = Blueprint('tenant', __name__, url_prefix='/kubernetes/tenant')


def _csrf() -> None:
    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError as exc:
        raise ValueError('The security token is missing or expired. Refresh the page and retry.') from exc


def _record(
    *,
    event_type: str,
    status: str,
    title: str,
    message: str,
    metadata: dict[str, Any],
    detail: str | None = None,
    queue_feedback: bool | None = None,
) -> dict[str, Any]:
    is_htmx = request.headers.get('HX-Request') == 'true'
    feedback = record_operational_activity(
        user_id=int(current_user.id),
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=url_for('tenant.index'),
        action_label='Open Tenant',
        action_icon='building-2',
        metadata={**metadata, 'operation_domain': 'kubernetes_tenant', 'feedback_delivery': 'toast'},
        queue_feedback=(not is_htmx) if queue_feedback is None else queue_feedback,
    )
    g.tenant_operational_feedback = feedback
    return feedback


def _tenant_workspace_context() -> dict[str, Any]:
    return {
        **get_tenant_context(),
        **get_tenant_access_context(),
        **get_tenant_workspace_context(),
        **get_tenant_sync_workspace_context(),
    }


_TENANT_ADMIN_SECTIONS = {
    'registry',
    'discovery',
    'tenant-setup',
    'memberships',
    'access-grants',
    'credentials',
    'namespace-access',
}


def _tenant_admin_section(value: str | None) -> str:
    normalized = str(value or 'registry').strip().lower()
    return normalized if normalized in _TENANT_ADMIN_SECTIONS else 'registry'


def _tenant_section_redirect(section: str):
    resolved_section = _tenant_admin_section(section)
    if request.headers.get('HX-Request') != 'true':
        return redirect(url_for('tenant.tenants', section=resolved_section))

    context = _tenant_workspace_context()
    context.update(get_tenant_summary_context())
    context.update(_tenant_active_section_context(resolved_section))
    rendered = render_template(
        'kubernetes/tenant/partials/_tenant_admin_workspace.html',
        active_tenant_section=resolved_section,
        can_manage=current_user.has_permission('tenant.manage'),
        **context,
    )
    feedback = getattr(g, 'tenant_operational_feedback', None)
    if feedback:
        rendered += render_template(
            'components/operational_toast.html',
            **feedback,
            toast_oob=True,
        )
    response = make_response(rendered)
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


def _tenant_active_section_context(section: str) -> dict[str, Any]:
    if section == 'registry':
        return {
            **get_tenant_registry_context(
                page=request.args.get('page', 1, type=int) or 1,
                per_page=request.args.get('per_page', 5, type=int) or 5,
                search=str(request.args.get('search') or ''),
                cluster_id=str(request.args.get('cluster_id') or ''),
                environment=str(request.args.get('environment') or ''),
                lifecycle_status=str(request.args.get('lifecycle_status') or ''),
            ),
        }
    if section == 'discovery':
        return {
            **get_tenant_discovery_context(
                page=request.args.get('discovery_page', 1, type=int) or 1,
                per_page=request.args.get('discovery_per_page', 5, type=int) or 5,
                cluster_id=str(request.args.get('discovery_cluster_id') or ''),
                provider=str(request.args.get('discovery_provider') or ''),
                management=str(request.args.get('discovery_management') or ''),
                search=str(request.args.get('discovery_search') or ''),
            ),
        }
    if section == 'memberships':
        return {
            **get_membership_registry_context(
                page=request.args.get('membership_page', 1, type=int) or 1,
                per_page=request.args.get('membership_per_page', 5, type=int) or 5,
                tenant_id=str(request.args.get('membership_tenant_id') or ''),
                principal_type=str(request.args.get('membership_principal_type') or ''),
                status=str(request.args.get('membership_status') or ''),
                search=str(request.args.get('membership_search') or ''),
            ),
            **get_group_registry_context(
                page=request.args.get('group_page', 1, type=int) or 1,
                per_page=request.args.get('group_per_page', 5, type=int) or 5,
                tenant_id=str(request.args.get('group_tenant_id') or ''),
                enabled=str(request.args.get('group_enabled') or ''),
                search=str(request.args.get('group_search') or ''),
            ),
        }
    if section == 'access-grants':
        return {
            **get_access_grant_registry_context(
                page=request.args.get('grant_page', 1, type=int) or 1,
                per_page=request.args.get('grant_per_page', 5, type=int) or 5,
                tenant_id=str(request.args.get('grant_tenant_id') or ''),
                status=str(request.args.get('grant_status') or ''),
                reconciliation_status=str(request.args.get('grant_reconciliation_status') or ''),
                scope_type=str(request.args.get('grant_scope_type') or ''),
                search=str(request.args.get('grant_search') or ''),
            ),
        }
    if section == 'credentials':
        return {
            **get_credential_registry_context(
                page=request.args.get('credential_page', 1, type=int) or 1,
                per_page=request.args.get('credential_per_page', 5, type=int) or 5,
                tenant_id=str(request.args.get('credential_tenant_id') or ''),
                credential_type=str(request.args.get('credential_type') or ''),
                status=str(request.args.get('credential_status') or ''),
                search=str(request.args.get('credential_search') or ''),
            ),
        }
    if section == 'namespace-access':
        return get_namespace_access_registry_context(
            page=request.args.get('namespace_access_page', 1, type=int) or 1,
            per_page=request.args.get('namespace_access_per_page', 5, type=int) or 5,
            tenant_id=str(request.args.get('namespace_access_tenant_id') or ''),
            environment=str(request.args.get('namespace_access_environment') or ''),
            credential_status=str(request.args.get('namespace_access_status') or ''),
            search=str(request.args.get('namespace_access_search') or ''),
        )
    return {}


def _required_int(name: str) -> int:
    value = str(request.form.get(name) or '').strip()
    if not value:
        raise ValueError(f'Select {name.replace("_", " ")}.')
    return int(value)


def _optional_int(name: str) -> int | None:
    value = str(request.form.get(name) or '').strip()
    return int(value) if value else None
