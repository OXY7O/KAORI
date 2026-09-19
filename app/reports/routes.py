import logging

from flask import Blueprint, render_template, url_for
from flask.typing import ResponseReturnValue
from werkzeug.exceptions import HTTPException

from app.access.rbac.decorators import permission_required
from app.reports.export.routes import (
    download_report_artifact,
    generate_report_output,
)
from app.reports.generate.routes import generate_report
from app.reports.generated.routes import (
    archive_generated_report,
    bulk_archive_generated_reports,
    generated_report_detail,
    generated_reports,
    restore_generated_report,
)
from app.reports.overview.presentation import normalize_reports_overview_payload
from app.reports.overview.service import get_reports_overview_payload
from app.reports.report_templates.routes import (
    create_report_template,
    delete_report_template,
    duplicate_custom_report_template,
    duplicate_system_report_template,
    report_templates,
    update_report_template,
)
from app.reports.schedules.routes import (
    create_schedule,
    delete_schedule,
    run_schedule,
    schedules,
    toggle_schedule,
    update_schedule,
)
from app.reports.storage.routes import (
    scan_storage_integrity,
    storage,
    storage_verification_status,
    verify_storage,
)
from app.reports.web import render_reports_unavailable

logger = logging.getLogger(__name__)


reports_bp = Blueprint(
    'reports',
    __name__,
    url_prefix='/reports',
)


@reports_bp.errorhandler(Exception)
def handle_reports_exception(exc: Exception) -> ResponseReturnValue:
    if isinstance(exc, HTTPException):
        return exc
    logger.error(
        'Unhandled Reports workspace failure.',
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return render_reports_unavailable(
        page_title='Reports Temporarily Unavailable',
        description='KAORI could not complete reporting while preserving report records and error boundaries safely.',
        reason='A reporting dependency did not respond. The technical exception was recorded in server logs and is not exposed to the user.',
        retry_url=url_for('reports.overview'),
    )


@reports_bp.route('/')
@permission_required('reports.view')
def overview() -> ResponseReturnValue:
    try:
        payload = normalize_reports_overview_payload(get_reports_overview_payload())
    except HTTPException:
        raise
    except Exception:
        logger.exception('Reports Overview could not be loaded.')
        return render_reports_unavailable(
            page_title='Reports Overview',
            description='Review reporting readiness, activity, artifacts, and data coverage while dependencies recover.',
            reason='KAORI could not load the reporting overview. Report records remain protected while storage or database connectivity is reviewed.',
            retry_url=url_for('reports.overview'),
        )

    return render_template(
        'reports/overview/index.html',
        payload=payload,
    )


reports_bp.add_url_rule(
    '/generated',
    endpoint='generated_reports',
    view_func=generated_reports,
    methods=[
        'GET',
    ],
)

reports_bp.add_url_rule(
    '/generated/<int:report_id>',
    endpoint='generated_report_detail',
    view_func=generated_report_detail,
    methods=[
        'GET',
    ],
)

reports_bp.add_url_rule(
    '/generated/<int:report_id>/generate-artifact',
    endpoint='generate_report_output',
    view_func=generate_report_output,
    methods=[
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/generated/<int:report_id>/download-artifact',
    endpoint='download_report_artifact',
    view_func=download_report_artifact,
    methods=[
        'GET',
    ],
)


reports_bp.add_url_rule(
    '/generated/bulk-archive',
    endpoint='bulk_archive_generated_reports',
    view_func=bulk_archive_generated_reports,
    methods=[
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/generated/<int:report_id>/archive',
    endpoint='archive_generated_report',
    view_func=archive_generated_report,
    methods=[
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/generated/<int:report_id>/restore',
    endpoint='restore_generated_report',
    view_func=restore_generated_report,
    methods=[
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/generate',
    endpoint='generate_report',
    view_func=generate_report,
    methods=[
        'GET',
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/templates',
    endpoint='report_templates',
    view_func=report_templates,
    methods=[
        'GET',
    ],
)

reports_bp.add_url_rule(
    '/templates/create',
    endpoint='create_report_template',
    view_func=create_report_template,
    methods=[
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/templates/<int:template_id>/update',
    endpoint='update_report_template',
    view_func=update_report_template,
    methods=[
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/templates/<int:template_id>/delete',
    endpoint='delete_report_template',
    view_func=delete_report_template,
    methods=[
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/templates/system/<string:template_id>/duplicate',
    endpoint='duplicate_system_template',
    view_func=duplicate_system_report_template,
    methods=[
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/templates/custom/<int:template_id>/duplicate',
    endpoint='duplicate_custom_template',
    view_func=duplicate_custom_report_template,
    methods=[
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/schedules',
    endpoint='schedules',
    view_func=schedules,
    methods=[
        'GET',
    ],
)

reports_bp.add_url_rule(
    '/schedules/create',
    endpoint='create_schedule',
    view_func=create_schedule,
    methods=[
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/schedules/<int:schedule_id>/update',
    endpoint='update_schedule',
    view_func=update_schedule,
    methods=[
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/schedules/<int:schedule_id>/toggle',
    endpoint='toggle_schedule',
    view_func=toggle_schedule,
    methods=[
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/schedules/<int:schedule_id>/delete',
    endpoint='delete_schedule',
    view_func=delete_schedule,
    methods=[
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/schedules/<int:schedule_id>/run-now',
    endpoint='run_schedule',
    view_func=run_schedule,
    methods=[
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/storage',
    endpoint='storage',
    view_func=storage,
    methods=[
        'GET',
    ],
)

reports_bp.add_url_rule(
    '/storage/verify',
    endpoint='verify_storage',
    view_func=verify_storage,
    methods=[
        'POST',
    ],
)

reports_bp.add_url_rule(
    '/storage/verification/status',
    endpoint='storage_verification_status',
    view_func=storage_verification_status,
    methods=[
        'GET',
    ],
)

reports_bp.add_url_rule(
    '/storage/integrity-scan',
    endpoint='scan_storage_integrity',
    view_func=scan_storage_integrity,
    methods=[
        'POST',
    ],
)
