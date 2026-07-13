from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.cluster.onboarding import has_registered_clusters
from app.kubernetes_operations.secrets.routes import (
    create_secret,
    secret_management_index,
    tls_secret_bulk_rotation_apply,
    tls_secret_bulk_rotation_page,
    tls_secret_bulk_rotation_preview,
    tls_secret_rotate,
    tls_secret_rotate_apply,
    tls_secret_rotate_preview,
)

kubernetes_operations_bp = Blueprint(
    'kubernetes_operations',
    __name__,
    url_prefix='/kubernetes-operations',
)


@kubernetes_operations_bp.before_request
def block_clusterless_operations():
    if has_registered_clusters() is not False:
        return None

    if request.method == 'GET':
        if request.headers.get('HX-Request') == 'true' or request.args.get('partial_mode'):
            return render_template('components/cluster/_onboarding_banner.html')
        return None

    if request.headers.get('HX-Request') == 'true':
        return render_template('components/cluster/_onboarding_banner.html')

    flash('Add a Kubernetes cluster before running Kubernetes operations.', 'warning')
    return redirect(url_for('cluster.index'))


kubernetes_operations_bp.add_url_rule(
    '/secrets',
    endpoint='secret_management',
    view_func=secret_management_index,
    methods=['GET'],
)


kubernetes_operations_bp.add_url_rule(
    '/secrets/create',
    endpoint='create_secret',
    view_func=create_secret,
    methods=['GET', 'POST'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/tls/<int:certificate_id>/rotate',
    endpoint='tls_secret_rotate',
    view_func=tls_secret_rotate,
    methods=['GET'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/tls/<int:certificate_id>/rotate/preview',
    endpoint='tls_secret_rotate_preview',
    view_func=tls_secret_rotate_preview,
    methods=['POST'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/tls/<int:certificate_id>/rotate/apply',
    endpoint='tls_secret_rotate_apply',
    view_func=tls_secret_rotate_apply,
    methods=['POST'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/tls-rotation',
    endpoint='tls_secret_bulk_rotation',
    view_func=tls_secret_bulk_rotation_page,
    methods=['GET'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/tls-rotation/preview',
    endpoint='tls_secret_bulk_rotation_preview',
    view_func=tls_secret_bulk_rotation_preview,
    methods=['POST'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/tls-rotation/apply',
    endpoint='tls_secret_bulk_rotation_apply',
    view_func=tls_secret_bulk_rotation_apply,
    methods=['POST'],
)
