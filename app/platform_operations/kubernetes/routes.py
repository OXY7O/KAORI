from __future__ import annotations

from flask import Blueprint, render_template, request, url_for

from app.platform_operations.kubernetes.presentation import build_kubernetes_administration_summary
from app.platform_operations.kubernetes.secret_reveal.service import (
    build_secret_reveal_settings_context,
)
from app.rbac.decorators import permission_required

bp = Blueprint('kubernetes', __name__)


def _active_administration_tab(value: str | None) -> str:
    normalized = (value or 'overview').strip().lower()
    return normalized if normalized in {'overview', 'secret-reveal'} else 'overview'


@bp.route('/')
@permission_required('kubernetes_secrets.manage_reveal')
def index():
    workspace_args = {
        key: value
        for key in ('cluster_id', 'namespace_q', 'namespace_policy', 'page', 'per_page')
        if (value := (request.args.get(key) or '').strip())
    }
    return render_template(
        'platform_operations/kubernetes/index.html',
        active_tab=_active_administration_tab(request.args.get('tab')),
        secret_reveal_workspace_url=url_for(
            'platform_operations.kubernetes.secret_reveal_tab_workspace',
            refresh_namespace='1',
            **workspace_args,
        ),
        **build_kubernetes_administration_summary(),
    )


@bp.route('/workspace/secret-reveal')
@permission_required('kubernetes_secrets.manage_reveal')
def secret_reveal_tab_workspace():
    context = build_secret_reveal_settings_context(
        request.args.get('cluster_id'),
        namespace_query=request.args.get('namespace_q'),
        namespace_policy_filter=request.args.get('namespace_policy'),
        page=request.args.get('page'),
        per_page=request.args.get('per_page'),
        refresh_namespace_source=request.args.get('refresh_namespace') == '1',
    )
    return render_template(
        'platform_operations/kubernetes/_secret_reveal_workspace.html',
        **context,
    )
