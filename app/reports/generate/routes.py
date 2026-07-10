from flask import flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.rbac.decorators import permission_required
from app.reports.generate.service import (
    create_report_request,
    get_form_state_from_form,
    get_generate_report_payload,
)


@permission_required('reports.generate')
def generate_report() -> ResponseReturnValue:
    if request.method == 'POST':
        user_id = getattr(
            current_user,
            'id',
            None,
        )

        success, errors, report = create_report_request(
            request.form,
            user_id,
        )

        if success and report is not None:
            flash(
                'Report request created successfully. You can generate the PDF from Generated Reports.',
                'success',
            )

            return redirect(
                url_for(
                    'reports.generated_reports',
                )
            )

        form_state = get_form_state_from_form(
            request.form,
        )

        payload = get_generate_report_payload(
            form_state=form_state,
            errors=errors,
        )

        for error in errors:
            flash(
                error,
                'error',
            )

        return render_template(
            'reports/generate/index.html',
            payload=payload,
        )

    form_state = get_form_state_from_form(
        request.args,
    )

    payload = get_generate_report_payload(
        form_state=form_state,
    )

    return render_template(
        'reports/generate/index.html',
        payload=payload,
    )
