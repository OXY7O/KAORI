from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue

from app.integrations.service import build_alertmanager_page, build_integrations_overview, build_kubernetes_detail, build_kubernetes_page, build_prometheus_page
from app.rbac.decorators import permission_required
from app.integrations.runtime.kubernetes_adapter import runtime_adapter as kubernetes_runtime_adapter
from app.integrations.runtime.monitoring import refresh_and_record
from app.integrations.runtime.repository import paginate_runtime_history
from app.integrations.runtime.presentation import runtime_history_view
from app.models.integration import KubernetesConnection

integrations_bp = Blueprint('integrations', __name__, url_prefix='/integrations')

@integrations_bp.get('/')
@permission_required('settings.manage_integrations')
def overview() -> ResponseReturnValue:
    context = build_integrations_overview(
        provider=request.args.get('provider', '').strip(),
        health=request.args.get('health', '').strip(),
        readiness=request.args.get('readiness', '').strip(),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    if request.headers.get('HX-Request') == 'true':
        return render_template('integrations/partials/_runtime_overview.html', **context)
    return render_template('integrations/overview.html', **context)


@integrations_bp.get('/kubernetes')
@permission_required('settings.manage_integrations')
def kubernetes() -> ResponseReturnValue:
    context = build_kubernetes_page(
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    return render_template('integrations/kubernetes.html', **context)


@integrations_bp.get('/kubernetes/<string:cluster_id>')
@permission_required('clusters.view')
def kubernetes_detail(cluster_id: str) -> ResponseReturnValue:
    context = build_kubernetes_detail(cluster_id)
    if context is None:
        abort(404)
    return render_template('integrations/kubernetes/detail.html', **context)


@integrations_bp.post('/kubernetes/<string:cluster_id>/runtime/refresh')
@permission_required('clusters.sync')
def kubernetes_runtime_refresh(cluster_id: str) -> ResponseReturnValue:
    connection = KubernetesConnection.query.filter_by(cluster_id=cluster_id).first_or_404()
    refresh_and_record(kubernetes_runtime_adapter, connection, trigger_type='manual')
    return redirect(url_for('integrations.kubernetes_detail', cluster_id=cluster_id))


@integrations_bp.get('/kubernetes/<string:cluster_id>/runtime/history')
@permission_required('clusters.view')
def kubernetes_runtime_history(cluster_id: str) -> ResponseReturnValue:
    connection = KubernetesConnection.query.filter_by(cluster_id=cluster_id).first_or_404()
    rows, pagination = paginate_runtime_history(
        'kubernetes',
        str(connection.id),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    return render_template(
        'integrations/kubernetes/partials/_runtime_history.html',
        history=runtime_history_view(rows, pagination=pagination),
        cluster=connection.cluster,
    )


@integrations_bp.get('/prometheus')
@permission_required('settings.manage_integrations')
def prometheus() -> ResponseReturnValue:
    context = build_prometheus_page(
        query=request.args.get('q', '').strip(),
        compatibility=request.args.get('compatibility', '').strip(),
        readiness=request.args.get('readiness', '').strip(),
        page=request.args.get('page', 1, type=int),
        per_page=request.args.get('per_page', 5, type=int),
    )
    if request.headers.get('HX-Request') == 'true':
        return render_template('integrations/prometheus/partials/_inventory_content.html', **context)
    return render_template('integrations/prometheus.html', **context)


@integrations_bp.get('/alertmanager')
@permission_required('settings.manage_integrations')
def alertmanager() -> ResponseReturnValue:
    context = build_alertmanager_page(
        query=request.args.get('q', '').strip(),
        readiness=request.args.get('readiness', '').strip(),
        deployment_type=request.args.get('deployment_type', '').strip(),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    if request.headers.get('HX-Request') == 'true':
        return render_template('integrations/alertmanager/partials/_inventory_content.html', **context)
    return render_template('integrations/alertmanager.html', **context)

