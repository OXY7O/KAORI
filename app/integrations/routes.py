from flask import Blueprint, redirect, render_template, url_for
from flask.typing import ResponseReturnValue

from app.integrations.service import build_alertmanager_page, build_integrations_overview, build_prometheus_page
from app.rbac.decorators import permission_required

integrations_bp = Blueprint('integrations', __name__, url_prefix='/integrations')
legacy_integrations_bp = Blueprint('legacy_integrations', __name__)


@integrations_bp.get('/')
@permission_required('settings.manage_integrations')
def overview() -> ResponseReturnValue:
    return render_template('integrations/overview.html', **build_integrations_overview())


@integrations_bp.get('/prometheus')
@permission_required('settings.manage_integrations')
def prometheus() -> ResponseReturnValue:
    return render_template('integrations/prometheus.html', **build_prometheus_page())


@integrations_bp.get('/alertmanager')
@permission_required('settings.manage_integrations')
def alertmanager() -> ResponseReturnValue:
    return render_template('integrations/alertmanager.html', **build_alertmanager_page())


@legacy_integrations_bp.get('/settings/prometheus')
@permission_required('settings.manage_integrations')
def legacy_settings_prometheus() -> ResponseReturnValue:
    return redirect(url_for('integrations.prometheus'), code=308)


@legacy_integrations_bp.get('/settings/alertmanager')
@permission_required('settings.manage_integrations')
def legacy_settings_alertmanager() -> ResponseReturnValue:
    return redirect(url_for('integrations.alertmanager'), code=308)


@legacy_integrations_bp.route('/prometheus/cluster/<string:cluster_id>', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def legacy_prometheus_config(cluster_id: str) -> ResponseReturnValue:
    return redirect(url_for('prometheus.configuration', cluster_id=cluster_id), code=307)


@legacy_integrations_bp.post('/prometheus/cluster/<string:cluster_id>/test')
@permission_required('settings.manage_integrations')
def legacy_prometheus_test(cluster_id: str) -> ResponseReturnValue:
    return redirect(url_for('prometheus.test_connection', cluster_id=cluster_id), code=307)


@legacy_integrations_bp.route('/alertmanager/cluster/<string:cluster_id>', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def legacy_alertmanager_config(cluster_id: str) -> ResponseReturnValue:
    return redirect(url_for('alertmanager.cluster_alertmanager_config', cluster_id=cluster_id), code=307)


@legacy_integrations_bp.post('/alertmanager/cluster/<string:cluster_id>/test')
@permission_required('settings.manage_integrations')
def legacy_alertmanager_test(cluster_id: str) -> ResponseReturnValue:
    return redirect(url_for('alertmanager.test_cluster_alertmanager', cluster_id=cluster_id), code=307)
