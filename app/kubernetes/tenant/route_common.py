from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, g, make_response, redirect, render_template, request, url_for
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
from app.kubernetes.tenant.service import (
    get_namespace_registry_context,
    get_tenant_registry_context,
    get_tenant_shell_context,
)
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


def _operations_active_tab() -> str:
    active_tab = str(request.args.get('tab') or 'provisioning')
    if active_tab == 'drift-reconcile':
        # Support existing bookmarked URLs until consumers adopt primary tabs.
        return 'operational-reconcile' if request.args.get('drift_view') == 'operations' else 'allocation-drift'
    if active_tab not in {
        'provisioning',
        'runs-evidence',
        'allocation-drift',
        'operational-reconcile',
        'activity',
    }:
        return 'provisioning'
    return active_tab


def _operations_provisioning_context() -> dict[str, Any]:
    namespace_context = get_namespace_registry_context(
        page=request.args.get('ops_namespace_page', 1, type=int) or 1,
        per_page=request.args.get('ops_namespace_per_page', 5, type=int) or 5,
        search=str(request.args.get('ops_namespace_search') or ''),
        tenant_id=str(request.args.get('ops_namespace_tenant_id') or ''),
        environment=str(request.args.get('ops_namespace_environment') or ''),
        status=str(request.args.get('ops_namespace_status') or ''),
        include_workflow_support=False,
    )
    return {
        'operations_namespace_rows': namespace_context['namespaces'],
        'operations_namespace_pagination': namespace_context['namespace_pagination'],
        'operations_namespace_filters': namespace_context['namespace_registry_filters'],
        'operations_namespace_tenant_options': namespace_context['namespace_registry_tenant_options'],
        'operations_namespace_environment_options': namespace_context['namespace_environment_filter_options'],
        'operations_namespace_status_options': namespace_context['namespace_status_filter_options'],
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


_REGISTRY_DETAIL_KEYS = (
    'page', 'per_page', 'search', 'cluster_id', 'environment', 'lifecycle_status',
)


def _tenant_detail_context(tenant_id: str) -> dict[str, Any]:
    """One exact committed Tenant for the detail page or HTMX refresh.

    Preserve only explicitly named Registry query fields, never an arbitrary
    return URL. The detail is not bound to a paginated/filtered Registry row.
    """
    context = get_tenant_registry_context(tenant_id=tenant_id, per_page=1)
    rows = context['tenant_rows']
    if not rows:
        abort(404)
    state: dict[str, str] = {
        key: str(request.values.get(f'registry_{key}') or '').strip()[:256]
        for key in _REGISTRY_DETAIL_KEYS
    }
    for key, fallback in (('page', 1), ('per_page', 5)):
        try:
            number = int(state[key])
        except ValueError:
            number = fallback
        state[key] = str(number if number > 0 else fallback)
    state['per_page'] = str(
        int(state['per_page']) if int(state['per_page']) in {5, 10, 25, 50} else 5
    )
    context['row'] = rows[0]
    context['registry_state'] = state
    # A detail POST reopens its governed section after the HTMX swap. If a
    # lifecycle transition makes it ineligible, use the next permitted view;
    # do not trust arbitrary form text to disclose an administrative panel.
    tenant = rows[0]['tenant']
    can_manage = current_user.has_permission('tenant.manage')
    can_integrate = current_user.has_permission('integrations.manage')
    can_cluster = current_user.has_permission('clusters.manage')
    admin = can_manage and can_integrate and can_cluster
    allowed_sections = {'provider', 'lifecycle'}
    if admin and tenant.ownership_status == 'adopted' and tenant.lifecycle_status == 'ready':
        allowed_sections.add('release')
    if (
        admin and tenant.provider_key == 'native_kubernetes'
        and tenant.lifecycle_status == 'released'
        and (tenant.provider_evidence_json or {}).get('release_governance', {}).get('release_mode') == 'managed_handoff'
    ):
        allowed_sections.add('handback')
    requested_section = str(request.values.get('tenant_detail_section') or '').strip()
    if requested_section in allowed_sections:
        active_section = requested_section
    elif requested_section == 'release' and 'handback' in allowed_sections:
        active_section = 'handback'
    else:
        active_section = 'release' if 'release' in allowed_sections else (
            'handback' if 'handback' in allowed_sections else 'provider'
        )
    context['tenant_detail_open_section'] = active_section
    # Wizard navigation is presentation only. No step is treated as approved,
    # executable, or complete without the existing committed checks/services.
    steps = ('scope', 'handoff', 'approval', 'finalize')
    requested_step = str(
        request.values.get('tenant_release_step')
        or request.values.get('release_step')
        or 'scope'
    ).strip().lower()
    context['tenant_release_step'] = (
        requested_step if requested_step in steps else 'scope'
    )
    context['tenant_release_step_index'] = steps.index(context['tenant_release_step']) + 1
    registry_query = {
        f'registry_{key}': value for key, value in state.items() if value
    }
    context['tenant_release_step_urls'] = {
        step: url_for(
            'tenant.tenant_detail',
            tenant_id=tenant_id,
            tenant_detail_section='release',
            release_step=step,
            _anchor='tenant-release-governance',
            **registry_query,
        )
        for step in steps
    }

    context['return_to_registry_url'] = url_for(
        'tenant.tenants',
        section='registry',
        **{f'registry_{key}': value for key, value in state.items() if value},
    )
    return context


def _tenant_section_redirect(section: str):
    resolved_section = _tenant_admin_section(section)
    detail_id = str(request.form.get('tenant_detail_id') or '').strip()
    if resolved_section == 'registry' and detail_id:
        context = _tenant_detail_context(detail_id)
        if request.headers.get('HX-Request') != 'true':
            return redirect(url_for(
                'tenant.tenant_detail', tenant_id=detail_id,
                tenant_detail_section=context['tenant_detail_open_section'],
                release_step=context['tenant_release_step']
                if context['tenant_detail_open_section'] == 'release' else None,
                _anchor={
                    'release': 'tenant-release-governance',
                    'handback': 'tenant-native-handback',
                    'provider': 'tenant-provider-authority',
                    'lifecycle': 'tenant-lifecycle-actions',
                }[context['tenant_detail_open_section']],
                **{f'registry_{key}': value for key, value in context['registry_state'].items() if value},
            ))
        feedback = getattr(g, 'tenant_operational_feedback', None)
        rendered = render_template(
            'kubernetes/tenant/partials/_tenant_management_detail.html',
            can_manage=current_user.has_permission('tenant.manage'),
            tenant_action_feedback=feedback,
            **context,
        )
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
    # Registry form POSTs inherit only prefixed context values from the selected
    # expandable panel. Keep those distinct from provider mutation form fields.
    def field(name: str, default: str = '') -> str:
        return str(
            request.values.get(f'registry_{name}')
            or request.values.get(name)
            or default
        )

    def number(name: str, default: int) -> int:
        try:
            value = int(field(name, str(default)))
        except ValueError:
            return default
        return value if value > 0 else default

    context = get_tenant_registry_context(
        page=number('page', 1),
        per_page=number('per_page', 5),
        search=field('search'),
        cluster_id=field('cluster_id'),
        environment=field('environment'),
        lifecycle_status=field('lifecycle_status'),
    )
    # Never render an arbitrary off-page Tenant solely because a caller supplied
    # its ID. The selected Tenant must belong to the current authorized registry.
    requested = str(request.values.get('manage_tenant_id') or '').strip()
    context['managed_tenant_id'] = (
        requested if any(str(row['tenant'].id) == requested for row in context['tenant_rows'])
        else ''
    )
    return context


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
