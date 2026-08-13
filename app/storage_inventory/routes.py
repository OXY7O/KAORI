from __future__ import annotations

from flask import Blueprint, abort, render_template, request
from flask.typing import ResponseReturnValue

from app.rbac.decorators import permission_required
from app.storage_inventory.presentation import (
    BucketFilters,
    SystemFilters,
    build_bucket_detail,
    build_buckets,
    build_overview,
    build_system_detail,
    build_systems,
)

object_storage_inventory_bp = Blueprint(
    'object_storage_inventory',
    __name__,
    url_prefix='/storage/object-storage',
)


def _workspace_template(resource: str) -> str:
    if request.headers.get('HX-Request') != 'true':
        return f'object_storage_inventory/{resource}/index.html'
    target = request.headers.get('HX-Target', '')
    partial_mode = request.args.get('partial_mode', '', type=str)
    if partial_mode == 'table_content' or target == f'object-storage-{resource}-table-content':
        return f'object_storage_inventory/{resource}/partials/_table_content.html'
    return f'object_storage_inventory/{resource}/partials/_page_workspace.html'


@object_storage_inventory_bp.get('/')
@permission_required('inventory.view')
def overview() -> ResponseReturnValue:
    overview_context = build_overview(
        system_page=request.args.get('system_page', 1, type=int) or 1,
        system_per_page=request.args.get('system_per_page', 5, type=int) or 5,
    )
    if (
        request.headers.get('HX-Request') == 'true'
        and request.headers.get('HX-Target') == 'object-storage-inventory-summary-content'
    ):
        return render_template(
            'object_storage_inventory/overview/partials/_systems_snapshot_content.html',
            overview=overview_context,
        )
    return render_template('object_storage_inventory/overview/index.html', overview=overview_context)


@object_storage_inventory_bp.get('/systems')
@permission_required('inventory.view')
def systems() -> ResponseReturnValue:
    filters = SystemFilters(
        search=request.args.get('search', '', type=str),
        product=request.args.get('product', '', type=str),
        native_type=request.args.get('native_type', '', type=str),
        environment=request.args.get('environment', '', type=str),
        status=request.args.get('status', '', type=str),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    inventory = build_systems(filters)
    return render_template(
        _workspace_template('systems'),
        inventory=inventory,
        search=filters.search,
        selected_product=filters.product,
        selected_native_type=filters.native_type,
        selected_environment=filters.environment,
        selected_status=filters.status,
    )


@object_storage_inventory_bp.get('/systems/<string:system_id>/details')
@permission_required('inventory.view')
def system_details(system_id: str) -> ResponseReturnValue:
    system = build_system_detail(system_id)
    if system is None:
        abort(404)
    return render_template('object_storage_inventory/systems/partials/_system_detail_content.html', system=system)


@object_storage_inventory_bp.get('/buckets')
@permission_required('inventory.view')
def buckets() -> ResponseReturnValue:
    filters = BucketFilters(
        search=request.args.get('search', '', type=str),
        system_id=request.args.get('system_id', '', type=str),
        product=request.args.get('product', '', type=str),
        native_type=request.args.get('native_type', '', type=str),
        environment=request.args.get('environment', '', type=str),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    inventory = build_buckets(filters)
    return render_template(
        _workspace_template('buckets'),
        inventory=inventory,
        search=filters.search,
        selected_system_id=filters.system_id,
        selected_product=filters.product,
        selected_native_type=filters.native_type,
        selected_environment=filters.environment,
    )


@object_storage_inventory_bp.get('/buckets/<int:bucket_id>/details')
@permission_required('inventory.view')
def bucket_details(bucket_id: int) -> ResponseReturnValue:
    bucket = build_bucket_detail(bucket_id)
    if bucket is None:
        abort(404)
    return render_template('object_storage_inventory/buckets/partials/_bucket_detail_content.html', bucket=bucket)
