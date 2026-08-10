from __future__ import annotations

from flask import Blueprint, render_template

from app.governance.tls_certificates.routes import (
    tls_certificates_detail,
    tls_certificates_index,
    tls_certificates_sync,
    tls_certificates_sync_status,
)
from app.rbac.decorators import permission_required

governance_bp = Blueprint(
    'governance',
    __name__,
    url_prefix='/governance',
)


@governance_bp.route('/', methods=['GET'])
@permission_required('governance.view')
def overview():
    return render_template('governance/overview/index.html')


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
