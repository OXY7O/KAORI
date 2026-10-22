"""Capability-owned operational Overview and bounded Inventory Evidence pages."""

from __future__ import annotations

from flask import Blueprint, render_template, request
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.access.rbac.decorators import permission_required
from app.dashboards.common.operational import normalize_operational_tab
from app.reports.catalog import REPORT_COVERAGE_DOMAINS
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
    coverage = next(
        (item for item in REPORT_COVERAGE_DOMAINS if item.key == 'secrets_pki'),
        None,
    ) if can_view_reports else None
    return render_template(
        'secrets_pki/overview.html',
        summary=build_secrets_pki_operational_summary(),
        active_tab=normalize_operational_tab(request.args.get('tab')),
        can_manage_integrations=current_user.has_permission('integrations.manage'),
        can_view_intelligence=current_user.has_permission('intelligence.view'),
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
    )
