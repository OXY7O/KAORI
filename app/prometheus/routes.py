from __future__ import annotations

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, url_for
from flask.typing import ResponseReturnValue

from app.cluster.service import get_cluster_by_id
from app.models import Cluster
from app.prometheus.exceptions import PrometheusError
from app.prometheus.forms import PrometheusConfigForm
from app.prometheus.service import PrometheusService
from app.rbac.decorators import permission_required

prometheus_bp = Blueprint(
    'prometheus',
    __name__,
    url_prefix='/prometheus',
)


def _get_cluster_or_404(
    cluster_id: str,
) -> Cluster:
    cluster = get_cluster_by_id(
        cluster_id,
    )

    if cluster is None:
        abort(
            404,
        )

    return cluster


@prometheus_bp.route(
    '/cluster/<string:cluster_id>',
    methods=[
        'GET',
        'POST',
    ],
)
@permission_required('settings.manage_integrations')
def configuration(
    cluster_id: str,
) -> ResponseReturnValue:
    cluster = _get_cluster_or_404(
        cluster_id,
    )

    config = cluster.prometheus_config

    form = PrometheusConfigForm()

    if form.validate_on_submit():
        try:
            PrometheusService.save_config(
                cluster,
                form,
            )

            flash(
                'Prometheus configuration saved',
                'success',
            )

            return redirect(
                url_for(
                    'prometheus.configuration',
                    cluster_id=cluster.id,
                )
            )

        except PrometheusError as exc:
            flash(
                str(
                    exc,
                ),
                'danger',
            )

    elif config:
        form.endpoint.data = config.endpoint
        form.auth_type.data = config.auth_type
        form.username.data = config.username
        form.password.data = config.password
        form.bearer_token.data = config.bearer_token
        form.timeout.data = config.timeout
        form.verify_ssl.data = config.verify_ssl

    return render_template(
        'prometheus/config.html',
        cluster=cluster,
        config=config,
        form=form,
    )


@prometheus_bp.route(
    '/cluster/<string:cluster_id>/test',
    methods=[
        'POST',
    ],
)
@permission_required('settings.manage_integrations')
def test_connection(
    cluster_id: str,
) -> ResponseReturnValue:
    cluster = _get_cluster_or_404(
        cluster_id,
    )

    try:
        service = PrometheusService(
            cluster,
        )

        return jsonify(
            service.test_connection(),
        )

    except PrometheusError as exc:
        return jsonify(
            {
                'success': False,
                'error': str(
                    exc,
                ),
            }
        ), 400
