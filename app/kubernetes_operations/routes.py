from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.cluster.onboarding import has_registered_clusters
from app.kubernetes_operations.configmaps.routes import (
    configmap_delete_target,
    configmap_editor,
    configmap_management_index,
    configmap_namespace_options,
    configmap_workspace,
    create_configmap_page,
    delete_configmap_page,
    update_configmap_page,
)
from app.kubernetes_operations.secrets.routes import (
    create_secret,
    replace_secret,
    replace_secret_content,
    replace_secret_workspace,
    reauthenticate_secret_reveal,
    request_secret_reveal,
    reveal_secret_content,
    reveal_secret_page,
    reveal_secret_status,
    reveal_secret_approvals,
    reveal_secret_value,
    reveal_secret_workspace,
    decide_secret_reveal_request,
    secret_management_index,
    secret_namespace_options,
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
    '/configmaps', endpoint='configmap_management', view_func=configmap_management_index, methods=['GET']
)
kubernetes_operations_bp.add_url_rule(
    '/configmaps/create', endpoint='create_configmap', view_func=create_configmap_page, methods=['GET', 'POST']
)
kubernetes_operations_bp.add_url_rule(
    '/configmaps/namespaces', endpoint='configmap_namespace_options', view_func=configmap_namespace_options, methods=['GET']
)
kubernetes_operations_bp.add_url_rule(
    '/configmaps/workspace', endpoint='configmap_workspace', view_func=configmap_workspace, methods=['GET']
)
kubernetes_operations_bp.add_url_rule(
    '/configmaps/editor', endpoint='configmap_editor', view_func=configmap_editor, methods=['GET']
)
kubernetes_operations_bp.add_url_rule(
    '/configmaps/delete-target', endpoint='configmap_delete_target', view_func=configmap_delete_target, methods=['GET']
)
kubernetes_operations_bp.add_url_rule(
    '/configmaps/update', endpoint='update_configmap', view_func=update_configmap_page, methods=['GET', 'POST']
)
kubernetes_operations_bp.add_url_rule(
    '/configmaps/delete', endpoint='delete_configmap', view_func=delete_configmap_page, methods=['GET', 'POST']
)

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
    '/secrets/create/namespaces',
    endpoint='secret_namespace_options',
    view_func=secret_namespace_options,
    methods=['GET'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/replace',
    endpoint='replace_secret',
    view_func=replace_secret,
    methods=['GET', 'POST'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/replace/workspace',
    endpoint='replace_secret_workspace',
    view_func=replace_secret_workspace,
    methods=['GET'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/replace/content',
    endpoint='replace_secret_content',
    view_func=replace_secret_content,
    methods=['GET'],
)


kubernetes_operations_bp.add_url_rule(
    '/secrets/reveal',
    endpoint='reveal_secret',
    view_func=reveal_secret_page,
    methods=['GET'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/reveal/status',
    endpoint='reveal_secret_status',
    view_func=reveal_secret_status,
    methods=['GET'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/reveal/approvals',
    endpoint='reveal_secret_approvals',
    view_func=reveal_secret_approvals,
    methods=['GET'],
)


kubernetes_operations_bp.add_url_rule(
    '/secrets/reveal/workspace',
    endpoint='reveal_secret_workspace',
    view_func=reveal_secret_workspace,
    methods=['GET'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/reveal/content',
    endpoint='reveal_secret_content',
    view_func=reveal_secret_content,
    methods=['GET'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/reveal/request',
    endpoint='request_secret_reveal',
    view_func=request_secret_reveal,
    methods=['POST'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/reveal/reauthenticate',
    endpoint='reauthenticate_secret_reveal',
    view_func=reauthenticate_secret_reveal,
    methods=['POST'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/reveal/requests/<string:request_id>/decision',
    endpoint='decide_secret_reveal_request',
    view_func=decide_secret_reveal_request,
    methods=['POST'],
)

kubernetes_operations_bp.add_url_rule(
    '/secrets/reveal/requests/<string:request_id>/value',
    endpoint='reveal_secret_value',
    view_func=reveal_secret_value,
    methods=['POST'],
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
