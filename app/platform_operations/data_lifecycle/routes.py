from __future__ import annotations

from flask import Blueprint, render_template, request, send_file
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.platform_operations.data_lifecycle.presentation import build_workspace_context
from app.platform_operations.data_lifecycle.service import (
    lifecycle_archive_download,
    queue_lifecycle_execution,
    update_lifecycle_policy,
    verify_lifecycle_archive,
)
from app.rbac.decorators import permission_required
from app.retention.domains import DOMAIN_FACTORIES

bp = Blueprint('data_lifecycle', __name__)


def _int(name: str, default: int) -> int:
    try:
        return int(request.values.get(name, default))
    except (TypeError, ValueError):
        return default


def _domain() -> str:
    value = str(request.values.get('domain') or 'operational_activity').strip().lower().replace('-', '_')
    return value if value in DOMAIN_FACTORIES else 'operational_activity'


def _context(*, feedback: dict | None = None, preview: bool = False) -> dict:
    return build_workspace_context(
        selected_domain=_domain(),
        active_tab=str(request.values.get('tab') or 'policies'),
        include_preview=preview or request.values.get('preview') == '1',
        archive_page=_int('archive_page', 1),
        archive_per_page=_int('archive_per_page', 5),
        archive_status=str(request.values.get('archive_status') or 'all'),
        archive_trigger=str(request.values.get('archive_trigger') or 'all'),
        archive_mode=str(request.values.get('archive_mode') or 'all'),
        archive_storage=str(request.values.get('archive_storage') or 'all'),
        archive_search=str(request.values.get('archive_search') or ''),
        archive_domain=str(request.values.get('archive_domain') or 'all'),
        feedback=feedback,
    )


@bp.get('/')
@permission_required('platform_operations.view_data_lifecycle')
def index() -> ResponseReturnValue:
    context = _context()
    if request.headers.get('HX-Request') == 'true':
        target = request.headers.get('HX-Target')
        if target == 'data-lifecycle-history':
            return render_template('platform_operations/data_lifecycle/partials/_history.html', lifecycle=context)
        if target == 'data-lifecycle-domain-workspace':
            return render_template(
                'platform_operations/data_lifecycle/partials/_domain_workspace.html', lifecycle=context
            )
    return render_template('platform_operations/data_lifecycle/index.html', lifecycle=context)


@bp.get('/preview')
@permission_required('platform_operations.view_data_lifecycle')
def preview() -> ResponseReturnValue:
    return render_template(
        'platform_operations/data_lifecycle/partials/_domain_workspace.html',
        lifecycle=_context(preview=True),
    )


@bp.post('/policy')
@permission_required('platform_operations.manage_data_lifecycle')
def save_policy() -> ResponseReturnValue:
    feedback = update_lifecycle_policy(
        domain_name=_domain(),
        values=request.form,
        user_id=current_user.id,
    )
    return render_template(
        'platform_operations/data_lifecycle/partials/_domain_workspace.html',
        lifecycle=_context(feedback=feedback),
    )


@bp.post('/run')
@permission_required('platform_operations.manage_data_lifecycle')
def run() -> ResponseReturnValue:
    feedback = queue_lifecycle_execution(
        domain_name=_domain(),
        mode=str(request.form.get('mode') or 'archive_only'),
        user_id=current_user.id,
    )
    return render_template(
        'platform_operations/data_lifecycle/partials/_domain_workspace.html',
        lifecycle=_context(feedback=feedback),
    )


@bp.post('/archives/<archive_id>/verify')
@permission_required('platform_operations.manage_data_lifecycle')
def verify(archive_id: str) -> ResponseReturnValue:
    context = _context(feedback=verify_lifecycle_archive(archive_id=archive_id, user_id=current_user.id))
    context['active_tab'] = 'history'
    return render_template('platform_operations/data_lifecycle/partials/_history.html', lifecycle=context)


@bp.get('/archives/<archive_id>/download')
@permission_required('platform_operations.export_data_lifecycle')
def download(archive_id: str) -> ResponseReturnValue:
    _artifact, path = lifecycle_archive_download(archive_id, kind=request.args.get('kind', 'data'))
    return send_file(path, as_attachment=True, download_name=path.name)
