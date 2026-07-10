from flask import flash, redirect, request, send_file, url_for
from flask.typing import ResponseReturnValue

from app.rbac.decorators import permission_required
from app.reports.export.service import generate_pdf_for_report, get_download_file_path


@permission_required('reports.generate')
def generate_report_pdf(
    report_id: int,
) -> ResponseReturnValue:
    success, message = generate_pdf_for_report(
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


@permission_required('reports.view')
def download_report_pdf(
    report_id: int,
) -> ResponseReturnValue:
    success, message, file_path = get_download_file_path(
        report_id,
    )

    if not success or file_path is None:
        flash(
            message,
            'error',
        )

        return redirect(
            url_for(
                'reports.generated_report_detail',
                report_id=report_id,
            )
        )

    return send_file(
        file_path,
        as_attachment=True,
        download_name=file_path.name,
        mimetype='application/pdf',
    )
