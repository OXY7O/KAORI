from flask import flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.rbac.decorators import permission_required
from app.reports.report_templates.service import (
    create_custom_template,
    delete_custom_template,
    duplicate_custom_template,
    duplicate_system_template,
    get_report_templates_payload,
    update_custom_template,
)


@permission_required('reports.manage_templates')
def report_templates() -> ResponseReturnValue:
    payload = get_report_templates_payload(request.args)
    return render_template('reports/report_templates/index.html', payload=payload)


@permission_required('reports.manage_templates')
def create_report_template() -> ResponseReturnValue:
    user_id = getattr(current_user, 'id', None)
    success, errors, template = create_custom_template(request.form, user_id)
    if success and template is not None:
        flash('Custom report template created successfully.', 'success')
        return redirect(url_for('reports.report_templates', edit_template_id=template.id))

    for error in errors:
        flash(error, 'error')
    return redirect(url_for('reports.report_templates'))


@permission_required('reports.manage_templates')
def update_report_template(template_id: int) -> ResponseReturnValue:
    success, errors, template = update_custom_template(template_id, request.form)
    if success and template is not None:
        flash('Custom report template updated successfully.', 'success')
        return redirect(url_for('reports.report_templates', edit_template_id=template.id))

    for error in errors:
        flash(error, 'error')
    return redirect(url_for('reports.report_templates', edit_template_id=template_id))


@permission_required('reports.manage_templates')
def delete_report_template(template_id: int) -> ResponseReturnValue:
    success, message = delete_custom_template(template_id)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('reports.report_templates'))


@permission_required('reports.manage_templates')
def duplicate_system_report_template(template_id: str) -> ResponseReturnValue:
    user_id = getattr(current_user, 'id', None)
    success, message, template = duplicate_system_template(template_id, user_id)
    flash(message, 'success' if success else 'error')
    if template is not None:
        return redirect(url_for('reports.report_templates', edit_template_id=template.id))
    return redirect(url_for('reports.report_templates'))


@permission_required('reports.manage_templates')
def duplicate_custom_report_template(template_id: int) -> ResponseReturnValue:
    user_id = getattr(current_user, 'id', None)
    success, message, template = duplicate_custom_template(template_id, user_id)
    flash(message, 'success' if success else 'error')
    if template is not None:
        return redirect(url_for('reports.report_templates', edit_template_id=template.id))
    return redirect(url_for('reports.report_templates'))
