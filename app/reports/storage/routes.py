from flask import flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue

from app.rbac.decorators import permission_required
from app.reports.storage.service import (
    build_report_cleanup_dry_run,
    get_report_storage_payload,
    scan_report_storage_integrity,
    verify_active_report_storage,
)


@permission_required('reports.manage_storage')
def storage() -> ResponseReturnValue:
    if (
        request.args.get(
            'cleanup_dry_run',
        )
        == '1'
    ):
        payload = get_report_storage_payload()
        payload['cleanup_dry_run_result'] = build_report_cleanup_dry_run()

        return render_template(
            'reports/storage/index.html',
            payload=payload,
        )

    if (
        request.args.get(
            'integrity',
        )
        == '1'
    ):
        payload = get_report_storage_payload()
        payload['integrity_result'] = scan_report_storage_integrity()

        return render_template(
            'reports/storage/index.html',
            payload=payload,
        )

    if (
        request.args.get(
            'verify',
        )
        == '1'
    ):
        try:
            result = verify_active_report_storage()
        except Exception as exc:
            flash(
                f'Storage verification failed: {exc}',
                'danger',
            )
        else:
            if result.get(
                'verified',
            ):
                flash(
                    f"Storage verification succeeded for {result.get('backend')} backend.",
                    'success',
                )
            else:
                flash(
                    'Storage verification completed, but the verification object could not be confirmed.',
                    'warning',
                )

        return redirect(
            url_for(
                'reports.storage',
            )
        )

    payload = get_report_storage_payload()

    return render_template(
        'reports/storage/index.html',
        payload=payload,
    )
