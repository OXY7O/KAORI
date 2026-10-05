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
from app.kubernetes.tenant.service import get_tenant_registry_context, get_tenant_shell_context
from app.kubernetes.tenant.workspace import (
    get_tenant_sync_workspace_context,
    get_tenant_workspace_context,
)
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


def _tenant_workspace_context(*, include_sync: bool = True) -> dict[str, Any]:
    context = get_tenant_shell_context()
    if include_sync:
        context.update(get_tenant_sync_workspace_context())
    return context


def _tenant_admin_support_context(section: str) -> dict[str, Any]:
    if section in {'memberships', 'access-grants'}:
        return get_tenant_access_context()
    if section == 'credentials':
        return {
            **get_tenant_access_context(),
            **get_tenant_workspace_context(),
        }
    return {}


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

    context = _tenant_workspace_context(include_sync=False)
    context.update(get_tenant_summary_context())
    context.update(_tenant_admin_support_context(resolved_section))
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


def _query_int(name: str, default: int = 1) -> int:
    return request.args.get(name, default, type=int) or default


def _query_text(name: str) -> str:
    return str(request.args.get(name) or '')


def _registry_section_context() -> dict[str, Any]:
    return get_tenant_registry_context(
        page=_query_int('page'),
        per_page=_query_int('per_page', 5),
        search=_query_text('search'),
        cluster_id=_query_text('cluster_id'),
        environment=_query_text('environment'),
        lifecycle_status=_query_text('lifecycle_status'),
    )


def _discovery_section_context() -> dict[str, Any]:
    return get_tenant_discovery_context(
        page=_query_int('discovery_page'),
        per_page=_query_int('discovery_per_page', 5),
        cluster_id=_query_text('discovery_cluster_id'),
        provider=_query_text('discovery_provider'),
        management=_query_text('discovery_management'),
        search=_query_text('discovery_search'),
    )


def _memberships_section_context() -> dict[str, Any]:
    return {
        **get_membership_registry_context(
            page=_query_int('membership_page'),
            per_page=_query_int('membership_per_page', 5),
            tenant_id=_query_text('membership_tenant_id'),
            principal_type=_query_text('membership_principal_type'),
            status=_query_text('membership_status'),
            search=_query_text('membership_search'),
        ),
        **get_group_registry_context(
            page=_query_int('group_page'),
            per_page=_query_int('group_per_page', 5),
            tenant_id=_query_text('group_tenant_id'),
            enabled=_query_text('group_enabled'),
            search=_query_text('group_search'),
        ),
    }


def _access_grants_section_context() -> dict[str, Any]:
    return get_access_grant_registry_context(
        page=_query_int('grant_page'),
        per_page=_query_int('grant_per_page', 5),
        tenant_id=_query_text('grant_tenant_id'),
        status=_query_text('grant_status'),
        reconciliation_status=_query_text('grant_reconciliation_status'),
        scope_type=_query_text('grant_scope_type'),
        search=_query_text('grant_search'),
    )


def _credentials_section_context() -> dict[str, Any]:
    return get_credential_registry_context(
        page=_query_int('credential_page'),
        per_page=_query_int('credential_per_page', 5),
        tenant_id=_query_text('credential_tenant_id'),
        credential_type=_query_text('credential_type'),
        status=_query_text('credential_status'),
        search=_query_text('credential_search'),
    )


def _namespace_access_section_context() -> dict[str, Any]:
    return get_namespace_access_registry_context(
        page=_query_int('namespace_access_page'),
        per_page=_query_int('namespace_access_per_page', 5),
        tenant_id=_query_text('namespace_access_tenant_id'),
        environment=_query_text('namespace_access_environment'),
        credential_status=_query_text('namespace_access_status'),
        search=_query_text('namespace_access_search'),
    )


_TENANT_SECTION_CONTEXT_BUILDERS = {
    'registry': _registry_section_context,
    'discovery': _discovery_section_context,
    'memberships': _memberships_section_context,
    'access-grants': _access_grants_section_context,
    'credentials': _credentials_section_context,
    'namespace-access': _namespace_access_section_context,
}


def _tenant_active_section_context(section: str) -> dict[str, Any]:
    builder = _TENANT_SECTION_CONTEXT_BUILDERS.get(section)
    return builder() if builder is not None else {}


def _required_int(name: str) -> int:
    value = str(request.form.get(name) or '').strip()
    if not value:
        raise ValueError(f'Select {name.replace("_", " ")}.')
    return int(value)


def _optional_int(name: str) -> int | None:
    value = str(request.form.get(name) or '').strip()
    return int(value) if value else None
