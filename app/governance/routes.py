from __future__ import annotations

from flask import Blueprint, render_template

from app.governance.tls_certificates.routes import (
    tls_certificates_bulk_apply,
    tls_certificates_bulk_page,
    tls_certificates_bulk_preview,
    tls_certificates_detail,
    tls_certificates_index,
    tls_certificates_sync,
    tls_certificates_update_apply,
    tls_certificates_update_preview,
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
    '/tls-certificates/<int:certificate_id>',
    endpoint='tls_certificates_detail',
    view_func=tls_certificates_detail,
    methods=['GET'],
)

governance_bp.add_url_rule(
    '/tls-certificates/<int:certificate_id>/update/preview',
    endpoint='tls_certificates_update_preview',
    view_func=tls_certificates_update_preview,
    methods=['POST'],
)

governance_bp.add_url_rule(
    '/tls-certificates/<int:certificate_id>/update/apply',
    endpoint='tls_certificates_update_apply',
    view_func=tls_certificates_update_apply,
    methods=['POST'],
)

governance_bp.add_url_rule(
    '/tls-certificates/bulk-update',
    endpoint='tls_certificates_bulk_update',
    view_func=tls_certificates_bulk_page,
    methods=['GET'],
)

governance_bp.add_url_rule(
    '/tls-certificates/bulk-update/preview',
    endpoint='tls_certificates_bulk_preview',
    view_func=tls_certificates_bulk_preview,
    methods=['POST'],
)

governance_bp.add_url_rule(
    '/tls-certificates/bulk-update/apply',
    endpoint='tls_certificates_bulk_apply',
    view_func=tls_certificates_bulk_apply,
    methods=['POST'],
)
