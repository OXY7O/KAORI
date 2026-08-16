import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import (
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import current_user
from werkzeug.exceptions import HTTPException

from app.auth.session import safe_next_url
from app.notifications.service import queue_transient_feedback, record_operational_activity
from app.rbac.decorators import permission_required
from app.reports.report_templates.service import (
    create_custom_template,
    delete_custom_template,
    duplicate_custom_template,
    duplicate_system_template,
    get_report_templates_payload,
    update_custom_template,
)
from app.reports.web import render_reports_unavailable

logger = logging.getLogger(__name__)


def _template_registry_return_url(value: object) -> str:
    registry_url = url_for('reports.report_templates')
    candidate = safe_next_url(value)
    if candidate == registry_url or (candidate and candidate.startswith(f'{registry_url}?')):
        return candidate
    return registry_url


def _template_edit_url(registry_url: str, template_id: int) -> str:
    parsed = urlsplit(registry_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query['edit_template_id'] = str(template_id)
    return urlunsplit(('', '', parsed.path, urlencode(query), ''))


def _template_registry_url_without_edit(registry_url: str) -> str:
    parsed = urlsplit(registry_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.pop('edit_template_id', None)
    return urlunsplit(('', '', parsed.path, urlencode(query), ''))


def _current_user_id() -> int:
    return int(getattr(current_user, 'id', 0) or 0)


def _queue_template_validation(errors: list[str]) -> None:
    queue_transient_feedback(
        status='error',
        title='Report Template Validation Failed',
        message='Review the report template fields and try again.',
        detail=' '.join(errors),
    )


def _record_template_feedback(
    *,
    event_type: str,
    success: bool,
    title: str,
    message: str,
    template_id: int | str | None = None,
    registry_return_url: str | None = None,
) -> None:
    action_url = _template_registry_return_url(registry_return_url)
    if isinstance(template_id, int):
        action_url = _template_edit_url(action_url, template_id)
    metadata: dict[str, object] = {'outcome': 'success' if success else 'failed'}
    if template_id is not None:
        metadata['template_id'] = template_id
    record_operational_activity(
        user_id=_current_user_id(),
        event_type=event_type,
        status='success' if success else 'error',
        title=title,
        message=message,
        action_url=action_url,
        action_label='View Report Templates',
        metadata=metadata,
        queue_feedback=True,
    )


@permission_required('reports.manage_templates')
def report_templates() -> ResponseReturnValue:
    try:
        payload = get_report_templates_payload(request.args)
    except HTTPException:
        raise
    except Exception:
        logger.exception('Report Templates could not be loaded.')
        return render_reports_unavailable(
            page_title='Report Templates',
            description='Manage reusable report structures and section contracts.',
            reason='KAORI could not load the template catalog. Existing templates remain unchanged while dependencies are reviewed.',
            retry_url=url_for('reports.report_templates'),
        )
    return render_template('reports/report_templates/index.html', payload=payload)


@permission_required('reports.manage_templates')
def create_report_template() -> ResponseReturnValue:
    registry_return_url = _template_registry_return_url(request.form.get('next'))
    success, errors, template = create_custom_template(request.form, _current_user_id())
    if success and template is not None:
        _record_template_feedback(
            event_type='report_template_create',
            success=True,
            title='Report Template Created',
            message='Custom report template created successfully.',
            template_id=template.id,
            registry_return_url=registry_return_url,
        )
        return redirect(_template_edit_url(registry_return_url, template.id))

    _queue_template_validation(errors)
    return redirect(registry_return_url)


@permission_required('reports.manage_templates')
def update_report_template(template_id: int) -> ResponseReturnValue:
    registry_return_url = _template_registry_return_url(request.form.get('next'))
    success, errors, template = update_custom_template(template_id, request.form)
    if success and template is not None:
        _record_template_feedback(
            event_type='report_template_update',
            success=True,
            title='Report Template Updated',
            message='Custom report template updated successfully.',
            template_id=template.id,
            registry_return_url=registry_return_url,
        )
        return redirect(_template_edit_url(registry_return_url, template.id))

    _queue_template_validation(errors)
    return redirect(_template_edit_url(registry_return_url, template_id))


@permission_required('reports.manage_templates')
def delete_report_template(template_id: int) -> ResponseReturnValue:
    registry_return_url = _template_registry_url_without_edit(_template_registry_return_url(request.form.get('next')))
    success, message = delete_custom_template(template_id)
    _record_template_feedback(
        event_type='report_template_delete',
        success=success,
        title='Report Template Deleted' if success else 'Report Template Deletion Failed',
        message=message,
        template_id=template_id,
        registry_return_url=registry_return_url,
    )
    return redirect(registry_return_url)


@permission_required('reports.manage_templates')
def duplicate_system_report_template(template_id: str) -> ResponseReturnValue:
    registry_return_url = _template_registry_return_url(request.form.get('next'))
    success, message, template = duplicate_system_template(template_id, _current_user_id())
    result_id = template.id if template is not None else template_id
    _record_template_feedback(
        event_type='report_template_duplicate',
        success=success,
        title='Report Template Duplicated' if success else 'Report Template Duplication Failed',
        message=message,
        template_id=result_id,
        registry_return_url=registry_return_url,
    )
    if template is not None:
        return redirect(_template_edit_url(registry_return_url, template.id))
    return redirect(registry_return_url)


@permission_required('reports.manage_templates')
def duplicate_custom_report_template(template_id: int) -> ResponseReturnValue:
    registry_return_url = _template_registry_return_url(request.form.get('next'))
    success, message, template = duplicate_custom_template(template_id, _current_user_id())
    result_id = template.id if template is not None else template_id
    _record_template_feedback(
        event_type='report_template_duplicate',
        success=success,
        title='Report Template Duplicated' if success else 'Report Template Duplication Failed',
        message=message,
        template_id=result_id,
        registry_return_url=registry_return_url,
    )
    if template is not None:
        return redirect(_template_edit_url(registry_return_url, template.id))
    return redirect(registry_return_url)
