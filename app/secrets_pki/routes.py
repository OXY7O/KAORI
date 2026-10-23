"""Capability-owned operational Overview and bounded Inventory Evidence pages."""

from __future__ import annotations

from flask import Blueprint, render_template, request
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.access.rbac.decorators import permission_required
from app.dashboards.common.operational import normalize_operational_tab
from app.reports.catalog import REPORT_COVERAGE_DOMAINS
from app.secrets_pki.binding_coverage import (
    build_vault_alert_source_sample_summary,
    build_vault_binding_coverage,
)
from app.secrets_pki.certificate_delivery_read_model import build_certificate_delivery_overlap
from app.secrets_pki.kv2_version_posture import build_kv2_version_posture
from app.secrets_pki.pki_presentation import pki_public_readiness
from app.secrets_pki.pki_stored_presentation import stored_pki_certificate_readiness
from app.secrets_pki.pki_validity_posture import build_stored_pki_validity_posture
from app.secrets_pki.presentation import build_secrets_pki_operational_summary

secrets_pki_bp = Blueprint('secrets_pki', __name__, url_prefix='/secrets-pki')


@secrets_pki_bp.get('/')
@permission_required('secrets_pki.view')
def overview() -> ResponseReturnValue:
    can_view_reports = current_user.has_permission('reports.view')
    can_view_intelligence = current_user.has_permission('intelligence.view')
    coverage = None
    if can_view_reports:
        coverage = next(
            (item for item in REPORT_COVERAGE_DOMAINS if item.key == 'secrets_pki'),
            None,
        )
    return render_template(
        'secrets_pki/overview.html',
        summary=build_secrets_pki_operational_summary(),
        binding_coverage=build_vault_binding_coverage(),
        alert_source_sample=(
            build_vault_alert_source_sample_summary() if can_view_intelligence else None
        ),
        active_tab=normalize_operational_tab(request.args.get('tab')),
        can_manage_integrations=current_user.has_permission('integrations.manage'),
        can_view_intelligence=can_view_intelligence,
        can_view_analytics=current_user.has_permission('analytics.view'),
        can_view_reports=can_view_reports,
        report_coverage=coverage,
    )


@secrets_pki_bp.get('/inventory')
@permission_required('secrets_pki.view')
def inventory() -> ResponseReturnValue:
    return render_template(
        'secrets_pki/inventory.html',
        summary=build_secrets_pki_operational_summary(),
        pki_readiness=pki_public_readiness(),
        kv2_version_posture=build_kv2_version_posture(),
        stored_cert_readiness=stored_pki_certificate_readiness(),
        pki_validity=build_stored_pki_validity_posture(),
        delivery_overlap=build_certificate_delivery_overlap(
            authorized_to_view_kubernetes_tls=current_user.has_permission('tls_certificates.view'),
        ),
        can_manage_integrations=current_user.has_permission('integrations.manage'),
        can_execute_inventory=current_user.has_permission('secrets_pki.sync')
        and current_user.has_permission('jobs.execute'),
        can_view_analytics=current_user.has_permission('analytics.view'),
    )


@secrets_pki_bp.get('/analytics/certificates')
@permission_required('secrets_pki.view')
@permission_required('analytics.view')
def certificate_analytics() -> ResponseReturnValue:
    """A current-generation public-PKI expiry snapshot, not a time-series."""
    return render_template(
        'secrets_pki/analytics/certificates.html',
        pki_validity=build_stored_pki_validity_posture(),
    )


@secrets_pki_bp.get('/registry')
@permission_required('secrets_pki.view')
def scoped_registry() -> ResponseReturnValue:
    """Exact resource grant, audited committed KV v2 metadata only."""
    from app.secrets_pki.scoped_registry_web import scoped_registry_response

    return scoped_registry_response()


@secrets_pki_bp.get('/certificates')
@permission_required('secrets_pki.view')
def certificates() -> ResponseReturnValue:
    from app.secrets_pki.evidence_workspaces import build_pki_evidence_workspace

    return render_template(
        'secrets_pki/evidence_workspace.html',
        **build_pki_evidence_workspace(
            kind='certificates',
            can_view_kubernetes_tls=current_user.has_permission('tls_certificates.view'),
        ),
    )


@secrets_pki_bp.get('/pki')
@permission_required('secrets_pki.view')
def pki() -> ResponseReturnValue:
    from app.secrets_pki.evidence_workspaces import build_pki_evidence_workspace

    return render_template(
        'secrets_pki/evidence_workspace.html',
        **build_pki_evidence_workspace(kind='pki'),
    )


@secrets_pki_bp.get('/expiration')
@permission_required('secrets_pki.view')
def expiration() -> ResponseReturnValue:
    from app.secrets_pki.evidence_workspaces import build_pki_evidence_workspace

    return render_template(
        'secrets_pki/evidence_workspace.html',
        **build_pki_evidence_workspace(kind='expiration'),
    )


@secrets_pki_bp.get('/lifecycle')
@permission_required('secrets_pki.view')
def lifecycle() -> ResponseReturnValue:
    """Capability-level, cross-domain committed evidence without Secret identity reads."""
    return render_template(
        'secrets_pki/lifecycle.html',
        kv2_version_posture=build_kv2_version_posture(),
        pki_validity=build_stored_pki_validity_posture(),
        delivery_overlap=build_certificate_delivery_overlap(
            authorized_to_view_kubernetes_tls=current_user.has_permission('tls_certificates.view'),
        ),
        can_view_analytics=current_user.has_permission('analytics.view'),
    )
