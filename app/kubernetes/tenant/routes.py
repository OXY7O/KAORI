from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from kubernetes.client.rest import ApiException
from wtforms.validators import ValidationError

from app.access.rbac.decorators import any_permission_required, permission_required
from app.kubernetes.tenant.service import (
    TenantStateConflictError,
    create_resource_profile_committed,
    create_tenant_committed,
    get_tenant_context,
    provision_native_namespace_committed,
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
) -> None:
    record_operational_activity(
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
        queue_feedback=True,
    )


@tenant_bp.get('/')
@any_permission_required('tenant.view', 'tenant.manage')
def index():
    return render_template('kubernetes/tenant/overview.html', **get_tenant_context())


@tenant_bp.get('/tenants')
@any_permission_required('tenant.view', 'tenant.manage')
def tenants():
    return render_template('kubernetes/tenant/tenants.html', **get_tenant_context())


@tenant_bp.get('/resource-profiles')
@any_permission_required('tenant.view', 'tenant.manage')
def resource_profiles():
    return render_template('kubernetes/tenant/resource_profiles.html', **get_tenant_context())


@tenant_bp.get('/namespace-provisioning')
@any_permission_required('tenant.view', 'tenant.manage')
def namespace_provisioning():
    return render_template('kubernetes/tenant/namespace_provisioning.html', **get_tenant_context())


@tenant_bp.get('/operations')
@any_permission_required('tenant.view', 'tenant.manage')
def operations():
    operations_tab = request.args.get('tab', 'provisioning')
    if operations_tab not in {'provisioning', 'runs', 'drift', 'activity'}:
        operations_tab = 'provisioning'
    return render_template(
        'kubernetes/tenant/operations.html',
        operations_tab=operations_tab,
        **get_tenant_context(),
    )


@tenant_bp.post('/tenants')
@permission_required('tenant.manage')
def create_tenant_route():
    try:
        _csrf()
        tenant, environment = create_tenant_committed(request.form)
    except ValueError as exc:
        _record(
            event_type='kubernetes_tenant_create_failed',
            status='error',
            title='Tenant Creation Failed',
            message=str(exc),
            metadata={'cluster_id': request.form.get('cluster_id'), 'operation': 'create_tenant'},
        )
    except TenantStateConflictError as exc:
        current_app.logger.exception('Tenant creation conflicted with committed state.')
        _record(
            event_type='kubernetes_tenant_create_failed',
            status='error',
            title='Tenant Creation Failed',
            message=str(exc),
            detail='No provider mutation was performed by this failed request.',
            metadata={'cluster_id': request.form.get('cluster_id'), 'operation': 'create_tenant'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_created',
            status='success',
            title='Tenant Created',
            message=f'{tenant.name} is ready for Native Kubernetes namespace provisioning.',
            detail=f'{environment.environment.title()} · Native Kubernetes',
            metadata={
                'tenant_id': tenant.id,
                'cluster_id': tenant.cluster_id,
                'environment': environment.environment,
                'provider_key': tenant.provider_key,
                'operation': 'create_tenant',
            },
        )
    return redirect(url_for('tenant.tenants'))


@tenant_bp.post('/resource-profiles')
@permission_required('tenant.manage')
def create_resource_profile_route():
    try:
        _csrf()
        profile = create_resource_profile_committed(request.form)
    except ValueError as exc:
        _record(
            event_type='kubernetes_tenant_resource_profile_create_failed',
            status='error',
            title='Resource Profile Creation Failed',
            message=str(exc),
            metadata={'operation': 'create_resource_profile'},
        )
    except TenantStateConflictError as exc:
        current_app.logger.exception('Tenant Resource Profile creation conflicted with committed state.')
        _record(
            event_type='kubernetes_tenant_resource_profile_create_failed',
            status='error',
            title='Resource Profile Creation Failed',
            message=str(exc),
            metadata={'operation': 'create_resource_profile'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_resource_profile_created',
            status='success',
            title='Resource Profile Created',
            message=f'{profile.name} is available for Tenant namespace provisioning.',
            detail=profile.profile_class.title(),
            metadata={
                'resource_profile_id': profile.public_id,
                'profile_class': profile.profile_class,
                'operation': 'create_resource_profile',
            },
        )
    return redirect(url_for('tenant.resource_profiles'))


@tenant_bp.post('/namespaces')
@permission_required('tenant.manage')
def provision_namespace_route():
    try:
        _csrf()
        record = provision_native_namespace_committed(request.form)
    except (ValueError, ApiException, TenantStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_namespace_provision_failed',
            status='error',
            title='Tenant Namespace Provisioning Failed',
            message=str(exc),
            metadata={
                'tenant_environment_id': request.form.get('tenant_environment_id'),
                'resource_profile_id': request.form.get('resource_profile_id'),
                'namespace': request.form.get('namespace'),
                'operation': 'provision_namespace',
            },
        )
    else:
        _record(
            event_type='kubernetes_tenant_namespace_provisioned',
            status='success' if record.provisioning_status == 'ready' else 'warning',
            title='Tenant Namespace Provisioned',
            message=f'{record.namespace} finished with {record.provisioning_status.title()} state.',
            detail=record.provisioning_message,
            metadata={
                'tenant_namespace_id': record.id,
                'cluster_id': record.cluster_id,
                'namespace': record.namespace,
                'provisioning_status': record.provisioning_status,
                'operation': 'provision_namespace',
            },
        )
    return redirect(url_for('tenant.namespace_provisioning'))
