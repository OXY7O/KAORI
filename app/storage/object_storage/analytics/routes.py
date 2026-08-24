from __future__ import annotations

from flask import render_template, request
from flask.typing import ResponseReturnValue

from app.access.rbac.decorators import permission_required
from app.storage.object_storage.analytics.service import (
    get_object_storage_alert_table_context,
    get_object_storage_analytics_context,
    get_object_storage_bucket_forecast_table_context,
    get_object_storage_bucket_table_context,
)


def _render(page_key: str) -> ResponseReturnValue:
    return render_template(
        'storage/object_storage/analytics/index.html',
        **get_object_storage_analytics_context(page_key, request.args),
    )


@permission_required('object_storage_analytics.view')
def object_storage_overview() -> ResponseReturnValue:
    return _render('overview')


@permission_required('object_storage_analytics.view')
def object_storage_capacity() -> ResponseReturnValue:
    return _render('capacity')


@permission_required('object_storage_analytics.view')
def object_storage_performance() -> ResponseReturnValue:
    return _render('performance')


@permission_required('object_storage_analytics.view')
def object_storage_forecast() -> ResponseReturnValue:
    return _render('forecast')


@permission_required('object_storage_analytics.view')
def object_storage_top_consumers() -> ResponseReturnValue:
    return _render('top_consumers')


@permission_required('object_storage_analytics.view')
def object_storage_recommendations() -> ResponseReturnValue:
    return _render('recommendations')


@permission_required('object_storage_analytics.view')
def object_storage_alerts() -> ResponseReturnValue:
    return _render('alerts')


@permission_required('object_storage_analytics.view')
def object_storage_bucket_table() -> ResponseReturnValue:
    page_key = str(request.args.get('page_key') or 'overview').strip()
    return render_template(
        'storage/object_storage/analytics/partials/_bucket_table.html',
        **get_object_storage_bucket_table_context(page_key, request.args),
    )


@permission_required('object_storage_analytics.view')
def object_storage_bucket_forecast_table() -> ResponseReturnValue:
    return render_template(
        'storage/object_storage/analytics/partials/_bucket_forecast_table.html',
        **get_object_storage_bucket_forecast_table_context(request.args),
    )


@permission_required('object_storage_analytics.view')
def object_storage_alert_table() -> ResponseReturnValue:
    return render_template(
        'storage/object_storage/analytics/partials/_alert_records.html',
        **get_object_storage_alert_table_context(request.args),
    )
