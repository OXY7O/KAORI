from __future__ import annotations

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue

from app.alertmanager.forms import parse_alertmanager_config_form
from app.alertmanager.service import (
    build_alertmanager_config_context,
    get_cluster_by_id,
    save_alertmanager_config,
    test_alertmanager_connection,
)
from app.rbac.decorators import permission_required

alertmanager_bp = Blueprint(
    'alertmanager',
    __name__,
    url_prefix='/alertmanager',
)


@alertmanager_bp.route(
    '/cluster/<string:cluster_id>',
    methods=[
        'GET',
        'POST',
    ],
)
@permission_required('settings.manage_integrations')
def cluster_alertmanager_config(
    cluster_id: str,
) -> ResponseReturnValue:
    cluster = get_cluster_by_id(
        cluster_id,
    )

    if cluster is None:
        abort(
            404,
        )

    if request.method == 'POST':
        form = parse_alertmanager_config_form(
            request.form,
        )

        if not form.endpoint:
            flash(
                'Alertmanager endpoint is required.',
                'error',
            )
        else:
            save_alertmanager_config(
                cluster_id=cluster_id,
                form=form,
            )

            action = request.form.get(
                'action',
                'save',
            )

            if action == 'save_test':
                result = test_alertmanager_connection(
                    cluster_id=cluster_id,
                )

                if result.get(
                    'connected',
                    False,
                ):
                    flash(
                        'Alertmanager configuration saved and connection test succeeded.',
                        'success',
                    )
                else:
                    flash(
                        f'Alertmanager configuration saved, but test failed: {result.get("error")}',
                        'error',
                    )
            else:
                flash(
                    'Alertmanager configuration saved.',
                    'success',
                )

            return redirect(
                url_for(
                    'alertmanager.cluster_alertmanager_config',
                    cluster_id=cluster_id,
                )
            )

    context = build_alertmanager_config_context(
        cluster_id=cluster_id,
    )

    return render_template(
        'alertmanager/config.html',
        **context,
    )


@alertmanager_bp.route(
    '/cluster/<string:cluster_id>/test',
    methods=[
        'POST',
    ],
)
@permission_required('settings.manage_integrations')
def test_cluster_alertmanager(
    cluster_id: str,
) -> ResponseReturnValue:
    cluster = get_cluster_by_id(
        cluster_id,
    )

    if cluster is None:
        abort(
            404,
        )

    result = test_alertmanager_connection(
        cluster_id=cluster_id,
    )

    return jsonify(
        {
            'success': result.get(
                'connected',
                False,
            ),
            'version': result.get(
                'version',
                'unknown',
            ),
            'response_time_ms': result.get(
                'response_time_ms',
                0,
            ),
            'error': result.get(
                'error',
            ),
        }
    )
