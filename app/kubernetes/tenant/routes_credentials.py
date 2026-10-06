from __future__ import annotations

import base64
from collections.abc import Callable
from typing import cast

from flask import abort, make_response, render_template, request
from flask_login import current_user
from kubernetes.client.rest import ApiException

from app.access.rbac.decorators import permission_required
from app.kubernetes.tenant.credential_service import (
    GeneratedKubeconfigMaterial,
    GeneratedTokenMaterial,
    HumanCredentialIssueRequest,
    TenantCredentialStateConflictError,
    create_human_credential_from_grant_committed,
    generate_credential_material_committed,
    renew_credential_committed,
    resume_credential_committed,
    revoke_credential_committed,
    suspend_credential_committed,
)
from app.kubernetes.tenant.deployer_credential_service import (
    DeployerCredentialIssueRequest,
    create_deployer_credential_committed,
)
from app.kubernetes.tenant.route_common import (
    _csrf,
    _record,
    _required_int,
    _tenant_section_redirect,
    _tenant_workspace_context,
    tenant_bp,
)
from app.models import User
from app.models.tenant import TenantCredential


@tenant_bp.post('/credentials/human')
@permission_required('tenant.manage')
def create_human_credential_route():
    try:
        _csrf()
        credential = create_human_credential_from_grant_committed(
            access_grant_id=_required_int('access_grant_id'),
            request=HumanCredentialIssueRequest(
                jumpserver_reference=str(request.form.get('jumpserver_reference') or ''),
                purpose=str(request.form.get('purpose') or 'interactive'),
            ),
            actor=cast(User, current_user),
        )
    except (ValueError, ApiException, TenantCredentialStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_credential_issue_failed',
            status='error',
            title='Tenant Human Credential Requires Attention',
            message=str(exc),
            metadata={'operation': 'credential_issue_human'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_credential_issued',
            status='success',
            title='Tenant Human Credential Issued',
            message=f'{credential.service_account_name} is ready for governed JumpServer delivery.',
            metadata={
                'credential_id': credential.id,
                'credential_public_id': credential.public_id,
                'operation': 'credential_issue_human',
            },
        )
    return _tenant_section_redirect('credentials')


@tenant_bp.post('/credentials/deployer')
@permission_required('tenant.manage')
def create_deployer_credential_route():
    try:
        _csrf()
        credential = create_deployer_credential_committed(
            tenant_namespace_id=_required_int('tenant_namespace_id'),
            owner_user_id=_required_int('owner_user_id'),
            request=DeployerCredentialIssueRequest(
                application_name=str(request.form.get('application_name') or ''),
                purpose=str(request.form.get('purpose') or 'github-actions-helm'),
            ),
            actor=cast(User, current_user),
        )
    except (ValueError, ApiException, TenantCredentialStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_deployer_credential_issue_failed',
            status='error',
            title='Tenant Deployer Credential Requires Attention',
            message=str(exc),
            metadata={'operation': 'credential_issue_deployer'},
        )
    else:
        _record(
            event_type='kubernetes_tenant_deployer_credential_issued',
            status='success',
            title='Tenant Deployer Credential Issued',
            message=f'{credential.service_account_name} is ready for governed CI/CD delivery.',
            metadata={
                'credential_id': credential.id,
                'credential_public_id': credential.public_id,
                'operation': 'credential_issue_deployer',
            },
        )
    return _tenant_section_redirect('credentials')


def _credential_feedback(
    *,
    action: str,
    credential_id: int,
    operation: Callable[..., TenantCredential],
) -> None:
    try:
        _csrf()
        credential = operation(credential_id=credential_id, actor=current_user)
    except (ValueError, ApiException, TenantCredentialStateConflictError) as exc:
        _record(
            event_type=f'kubernetes_tenant_credential_{action}_failed',
            status='error',
            title=f'Tenant Credential {action.title()} Requires Attention',
            message=str(exc),
            metadata={'credential_id': credential_id, 'operation': f'credential_{action}'},
        )
    else:
        _record(
            event_type=f'kubernetes_tenant_credential_{action}',
            status='success',
            title=f'Tenant Credential {action.title()}',
            message=f'{credential.service_account_name} is now {credential.status.replace("_", " ")}.',
            metadata={
                'credential_id': credential.id,
                'credential_public_id': credential.public_id,
                'operation': f'credential_{action}',
            },
        )


@tenant_bp.post('/credentials/<int:credential_id>/material')
@permission_required('tenant.manage')
def generate_credential_material_route(credential_id: int):
    try:
        _csrf()
        requested_seconds = _required_int('requested_seconds')
        material = generate_credential_material_committed(
            credential_id=credential_id,
            namespace_id=_required_int('namespace_id'),
            requested_seconds=requested_seconds,
            actor=cast(User, current_user),
        )
    except (ValueError, ApiException, TenantCredentialStateConflictError) as exc:
        _record(
            event_type='kubernetes_tenant_credential_material_failed',
            status='error',
            title='Credential Material Requires Attention',
            message=str(exc),
            metadata={'credential_id': credential_id, 'operation': 'credential_material_generate'},
        )
        return _tenant_section_redirect('credentials')

    context = _tenant_workspace_context()
    if isinstance(material, GeneratedTokenMaterial):
        material_kind = 'token'
        material_title = 'JumpServer ServiceAccount Token'
        material_value = material.token
        material_base64 = None
        delivery_label = 'Manual JumpServer delivery'
        page_title = 'One-Time Human Token'
        page_icon = 'user-key'
    elif isinstance(material, GeneratedKubeconfigMaterial):
        material_kind = 'kubeconfig'
        material_title = 'CI/CD Kubeconfig'
        material_value = material.kubeconfig
        material_base64 = base64.b64encode(material.kubeconfig.encode('utf-8')).decode('ascii')
        delivery_label = 'GitHub Actions / Helm'
        page_title = 'One-Time CI/CD Kubeconfig'
        page_icon = 'git-branch'
    else:
        abort(500)

    response = make_response(
        render_template(
            'kubernetes/tenant/credential_material.html',
            tenant_page='tenants',
            tenant_page_title=page_title,
            tenant_page_icon=page_icon,
            material_kind=material_kind,
            material_title=material_title,
            material_value=material_value,
            material_base64=material_base64,
            material_namespace=material.namespace,
            material_expires_at=material.expires_at,
            material_requested_seconds=requested_seconds,
            material_access_package=material.access_package,
            material_credential_valid_until=material.expires_at,
            delivery_label=delivery_label,
            **context,
        )
    )
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


@tenant_bp.post('/credentials/<int:credential_id>/renew')
@permission_required('tenant.manage')
def renew_credential_route(credential_id: int):
    _credential_feedback(action='renewed', credential_id=credential_id, operation=renew_credential_committed)
    return _tenant_section_redirect('credentials')


@tenant_bp.post('/credentials/<int:credential_id>/suspend')
@permission_required('tenant.manage')
def suspend_credential_route(credential_id: int):
    _credential_feedback(action='suspended', credential_id=credential_id, operation=suspend_credential_committed)
    return _tenant_section_redirect('credentials')


@tenant_bp.post('/credentials/<int:credential_id>/resume')
@permission_required('tenant.manage')
def resume_credential_route(credential_id: int):
    _credential_feedback(action='resumed', credential_id=credential_id, operation=resume_credential_committed)
    return _tenant_section_redirect('credentials')


@tenant_bp.post('/credentials/<int:credential_id>/revoke')
@permission_required('tenant.manage')
def revoke_credential_route(credential_id: int):
    _credential_feedback(action='revoked', credential_id=credential_id, operation=revoke_credential_committed)
    return _tenant_section_redirect('credentials')


def register_credential_routes() -> None:
    """Import marker for Tenant Credential route registration."""
