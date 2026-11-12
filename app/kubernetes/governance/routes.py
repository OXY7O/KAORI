from __future__ import annotations

from flask import Blueprint, render_template
from flask_login import current_user

from app.access.rbac.decorators import permission_required
from app.kubernetes.cluster.onboarding import has_registered_clusters
from app.kubernetes.governance.internal_certificates.routes import internal_certificates_index
from app.kubernetes.governance.tls_certificates.routes import (
    tls_certificates_detail,
    tls_certificates_index,
    tls_certificates_sync,
    tls_certificates_sync_status,
)
from app.kubernetes.governance.tls_certificates.service import get_tls_collection_snapshot

governance_bp = Blueprint(
    'governance',
    __name__,
    url_prefix='/governance',
)


@governance_bp.route('/', methods=['GET'])
@permission_required('governance.view')
def overview():
    can_view_tls = current_user.has_permission('tls_certificates.view')
    can_view_internal_certificates = current_user.has_permission('internal_certificates.view') and current_user.has_permission('clusters.view')
    tls_snapshot = None
    # Gate TLS evidence behind child authorization and registered-cluster readiness.
    if can_view_tls and has_registered_clusters() is True:
        tls_snapshot = get_tls_collection_snapshot()

    return render_template(
        'kubernetes/governance/overview/index.html',
        can_view_tls=can_view_tls,
        can_view_internal_certificates=can_view_internal_certificates,
        tls_snapshot=tls_snapshot,
    )


governance_bp.add_url_rule(
    '/tls-certificates',
    endpoint='tls_certificates',
    view_func=tls_certificates_index,
    methods=['GET'],
)

governance_bp.add_url_rule(
    '/tls-certificates/sync',
    endpoint='tls_certificates_sync',
    view_func=tls_certificates_sync,
    methods=['POST'],
)


governance_bp.add_url_rule(
    '/tls-certificates/sync/<string:public_id>/status',
    endpoint='tls_certificates_sync_status',
    view_func=tls_certificates_sync_status,
    methods=['GET'],
)

governance_bp.add_url_rule(
    '/tls-certificates/<int:certificate_id>',
    endpoint='tls_certificates_detail',
    view_func=tls_certificates_detail,
    methods=['GET'],
)


governance_bp.add_url_rule(
    '/internal-certificates',
    endpoint='internal_certificates',
    view_func=internal_certificates_index,
    methods=['GET'],
)
