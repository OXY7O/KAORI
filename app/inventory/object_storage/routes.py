from __future__ import annotations

from flask import Blueprint, abort, render_template, request
from flask.typing import ResponseReturnValue

from app.inventory.object_storage.presentation import (
    BucketFilters,
    SystemFilters,
    build_bucket_detail,
    build_buckets,
    build_overview,
    build_system_detail,
    build_systems,
)
from app.rbac.decorators import permission_required

object_storage_inventory_bp = Blueprint(
    'object_storage_inventory',
    __name__,
    url_prefix='/storage/object-storage',
)


def _workspace_template(resource: str) -> str:
    if request.headers.get('HX-Request') != 'true':
        return f'inventory/object_storage/{resource}/index.html'
    target = request.headers.get('HX-Target', '')
    partial_mode = request.args.get('partial_mode', '', type=str)
    if partial_mode == 'table_content' or target == f'object-storage-{resource}-table-content':
        return f'inventory/object_storage/{resource}/partials/_table_content.html'
    return f'inventory/object_storage/{resource}/partials/_page_workspace.html'


def _setup_blocked_htmx(inventory: dict[str, object]) -> ResponseReturnValue | None:
    setup = inventory.get('setup')
    if request.headers.get('HX-Request') == 'true' and isinstance(setup, dict) and setup.get('is_blocked') is True:
        return render_template('inventory/object_storage/components/_onboarding_banner.html')
    return None


@object_storage_inventory_bp.get('/')
@permission_required('object_storage_inventory.view')
def overview() -> ResponseReturnValue:
    overview_context = build_overview(
        system_page=request.args.get('system_page', 1, type=int) or 1,
        system_per_page=request.args.get('system_per_page', 5, type=int) or 5,
    )
    blocked_response = _setup_blocked_htmx(overview_context)
    if blocked_response is not None:
        return blocked_response
    if (
        request.headers.get('HX-Request') == 'true'
        and request.headers.get('HX-Target') == 'object-storage-inventory-summary-content'
    ):
        return render_template(
            'inventory/object_storage/overview/partials/_systems_snapshot_content.html',
            overview=overview_context,
        )
    return render_template('inventory/object_storage/overview/index.html', overview=overview_context)


@object_storage_inventory_bp.get('/systems')
@permission_required('object_storage_inventory.view')
def systems() -> ResponseReturnValue:
    filters = SystemFilters(
        search=request.args.get('search', '', type=str),
        provider=request.args.get('provider', '', type=str),
        environment=request.args.get('environment', '', type=str),
        status=request.args.get('status', '', type=str),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    inventory = build_systems(filters)
    blocked_response = _setup_blocked_htmx(inventory)
    if blocked_response is not None:
        return blocked_response
    return render_template(
        _workspace_template('systems'),
        inventory=inventory,
        search=filters.search,
        selected_provider=filters.provider,
        selected_environment=filters.environment,
        selected_status=filters.status,
    )


@object_storage_inventory_bp.get('/systems/<string:system_id>/details')
@permission_required('object_storage_inventory.view')
def system_details(system_id: str) -> ResponseReturnValue:
    system = build_system_detail(system_id)
    if system is None:
        abort(404)
    return render_template('inventory/object_storage/systems/partials/_system_detail_content.html', system=system)


@object_storage_inventory_bp.get('/buckets')
@permission_required('object_storage_inventory.view')
def buckets() -> ResponseReturnValue:
    filters = BucketFilters(
        search=request.args.get('search', '', type=str),
        system_id=request.args.get('system_id', '', type=str),
        provider=request.args.get('provider', '', type=str),
        native_type=request.args.get('native_type', '', type=str),
        environment=request.args.get('environment', '', type=str),
        page=request.args.get('page', 1, type=int) or 1,
        per_page=request.args.get('per_page', 5, type=int) or 5,
    )
    inventory = build_buckets(filters)
    blocked_response = _setup_blocked_htmx(inventory)
    if blocked_response is not None:
        return blocked_response
    return render_template(
        _workspace_template('buckets'),
        inventory=inventory,
        search=filters.search,
        selected_system_id=filters.system_id,
        selected_provider=filters.provider,
        selected_native_type=filters.native_type,
        selected_environment=filters.environment,
    )


@object_storage_inventory_bp.get('/buckets/<int:bucket_id>/details')
@permission_required('object_storage_inventory.view')
def bucket_details(bucket_id: int) -> ResponseReturnValue:
    bucket = build_bucket_detail(bucket_id)
    if bucket is None:
        abort(404)
    return render_template('inventory/object_storage/buckets/partials/_bucket_detail_content.html', bucket=bucket)
