from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user

from app.cluster.onboarding import has_registered_clusters
from app.governance.tls_certificates.routes import (
    tls_certificates_detail,
    tls_certificates_index,
    tls_certificates_sync,
)
from app.notifications.service import record_operational_activity
from app.rbac.decorators import permission_required

governance_bp = Blueprint(
    'governance',
    __name__,
    url_prefix='/governance',
)


@governance_bp.before_request
def block_clusterless_governance_actions():
    """Block Kubernetes governance partials and writes until a cluster exists."""
    if has_registered_clusters() is not False:
        return None

    if request.method == 'GET':
        if request.headers.get('HX-Request') == 'true' or request.args.get('partial_mode'):
            return render_template('components/cluster/_onboarding_banner.html')
        return None

    if request.headers.get('HX-Request') == 'true':
        return render_template('components/cluster/_onboarding_banner.html')

    record_operational_activity(
        user_id=current_user.id,
        event_type='governance_tls_cluster_required',
        status='warning',
        title='Kubernetes cluster setup required',
        message='Add a Kubernetes cluster before using TLS certificate governance actions in KAORI.',
        action_url=url_for('integrations.kubernetes'),
        queue_feedback=True,
    )
    return redirect(url_for('governance.tls_certificates'))


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
