from flask import flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue

from app.rbac.decorators import permission_required
from app.reports.generated.service import (
    archive_report_record,
    bulk_archive_report_records,
    get_generated_reports_payload,
    get_report_detail_payload,
    restore_archived_report_record,
)


@permission_required('reports.view')
def generated_reports() -> ResponseReturnValue:
    payload = get_generated_reports_payload(
        request.args,
    )

    return render_template(
        'reports/generated/index.html',
        payload=payload,
    )


@permission_required('reports.view')
def generated_report_detail(
    report_id: int,
) -> ResponseReturnValue:
    payload = get_report_detail_payload(
        report_id,
    )

    return render_template(
        'reports/generated/detail.html',
        payload=payload,
    )


@permission_required('reports.manage_storage')
def bulk_archive_generated_reports() -> ResponseReturnValue:
    success, message = bulk_archive_report_records(
        request.form.getlist(
            'report_ids',
        )
    )

    flash(
        message,
        'success' if success else 'error',
    )

    next_url = request.form.get(
        'next',
        '',
    )

    if next_url.startswith(
        '/reports/generated',
    ):
        return redirect(
            next_url,
        )

    return redirect(
        url_for(
            'reports.generated_reports',
        )
    )


@permission_required('reports.manage_storage')
def archive_generated_report(
    report_id: int,
) -> ResponseReturnValue:
    success, message = archive_report_record(
        report_id,
    )

    flash(
        message,
        'success' if success else 'error',
    )

    next_url = request.form.get(
        'next',
        '',
    )

    if next_url.startswith(
        '/reports/generated',
    ):
        return redirect(
            next_url,
        )

    return redirect(
        url_for(
            'reports.generated_report_detail',
            report_id=report_id,
        )
    )


@permission_required('reports.manage_storage')
def restore_generated_report(
    report_id: int,
) -> ResponseReturnValue:
    success, message = restore_archived_report_record(
        report_id,
    )

    flash(
        message,
        'success' if success else 'error',
    )

    next_url = request.form.get(
        'next',
        '',
    )

    if next_url.startswith(
        '/reports/generated',
    ):
        return redirect(
            next_url,
        )

    return redirect(
        url_for(
            'reports.generated_report_detail',
            report_id=report_id,
        )
    )
