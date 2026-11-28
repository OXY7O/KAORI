from __future__ import annotations

from typing import Any

from flask import make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.intelligence.alert_intelligence.service import get_alert_intelligence_payload


def index_response() -> ResponseReturnValue:
    payload = get_alert_intelligence_payload(request.args)
    if request.headers.get('HX-Request') == 'true':
        target = str(request.headers.get('HX-Target') or '').strip()
        if target == 'alert-channel-readiness-registry':
            if (
                payload.get('tab') != 'routing'
                or payload.get('provider_case_mode')
                or payload.get('channel_readiness') is None
            ):
                response = make_response('', 200)
                response.headers['HX-Redirect'] = url_for(
                    'alert_intelligence.index',
                    tab='routing',
                    domain=payload['domain'],
                    asset=payload.get('selected_asset_key') or '',
                    provider=payload.get('selected_provider') or '',
                )
                return response
            return render_template('intelligence/partials/_alert_channel_readiness_registry.html', payload=payload)
        # Scoped registry fragments may disappear when a grant is revoked or
        # evidence fails. Replace the whole document rather than leaving old
        # case rows, summary or action controls in the browser.
        if (
            payload.get('provider_case_mode')
            and (
                payload.get('provider_case_status') != 'ready'
                or (payload.get('tab') == 'routing' and payload.get('local_routing') is None)
            )
            and target != 'alert-intelligence-page-content'
        ):
            response = make_response('', 200)
            response.headers['HX-Redirect'] = url_for(
                'alert_intelligence.index',
                domain=payload['domain'],
                provider=payload.get('selected_provider') or '',
                asset=payload.get('selected_asset_key') or '',
                tab=payload['tab'],
            )
            return response
        if target == 'alert-operations-active-records':
            return render_template('intelligence/partials/_alert_ops_active_table.html', payload=payload)
        return render_template('intelligence/partials/_alert_intelligence_page.html', payload=payload)
    return render_template('intelligence/alert_intelligence.html', payload=payload)


def case_details_response(public_id: str) -> ResponseReturnValue:
    from app.intelligence.alert_intelligence.provider_case_scope import (
        is_provider_case_domain,
        provider_case_detail_response,
    )

    if is_provider_case_domain(str(request.args.get('domain') or '')):
        return provider_case_detail_response(request.args, public_id)
    args = request.args.copy()
    args['case'] = public_id
    if not args.get('tab'):
        args['tab'] = 'active'
    payload = get_alert_intelligence_payload(args)
    if payload.get('selected_case') is None:
        return ('Alert case not found.', 404)
    template = (
        'intelligence/partials/_alert_ops_resolved_case_modal.html'
        if payload.get('tab') == 'resolved'
        else 'intelligence/partials/_alert_ops_case_workspace.html'
    )
    return render_template(template, payload=payload, modal_refresh=False)


def actor_user_id() -> int | None:
    value = getattr(current_user, 'id', None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def optional_positive_int(value: Any) -> int | None:
    if value in (None, ''):
        return None
    try:
        parsed = int(str(value))
    except ValueError as exc:
        raise ValueError('Selected user or record identifier is invalid.') from exc
    if parsed < 1:
        raise ValueError('Selected user or record identifier is invalid.')
    return parsed


def parse_matchers(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in value.splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        if '=' not in normalized:
            raise ValueError('Routing matchers must use one key=value pair per line.')
        key, expected = normalized.split('=', 1)
        if not key.strip() or not expected.strip():
            raise ValueError('Routing matchers must use one key=value pair per line.')
        result[key.strip()] = expected.strip().strip('"')
    return result


def active_records_htmx_request() -> bool:
    return (
        request.headers.get('HX-Request') == 'true'
        and str(request.headers.get('HX-Target') or '').strip() == 'alert-operations-active-records'
    )


def active_records_response(*, case_id: str | None = None) -> ResponseReturnValue:
    args = request.form.copy()
    args['tab'] = 'active'
    if case_id:
        args['case'] = case_id
    else:
        args.pop('case', None)
    payload = get_alert_intelligence_payload(args)
    return render_template('intelligence/partials/_alert_ops_active_table.html', payload=payload)


def modal_case_htmx_request() -> bool:
    return request.headers.get('HX-Request') == 'true' and str(
        request.headers.get('HX-Target') or ''
    ).strip().startswith('alert-case-modal-content-')


def modal_case_response(*, case_id: str, tab: str | None = None) -> ResponseReturnValue:
    args = request.form.copy()
    args['case'] = case_id
    requested_tab = str(tab or request.form.get('tab') or 'active').strip().lower()
    args['tab'] = 'resolved' if requested_tab == 'resolved' else 'active'
    payload = get_alert_intelligence_payload(args)
    if payload.get('selected_case') is None:
        return ('Alert case unavailable.', 404)
    template = (
        'intelligence/partials/_alert_ops_resolved_case_modal.html'
        if payload.get('tab') == 'resolved'
        else 'intelligence/partials/_alert_ops_case_workspace.html'
    )
    response = make_response(
        render_template(
            template,
            payload=payload,
            modal_refresh=True,
        )
    )
    response.headers['HX-Trigger'] = 'alertCaseChanged'
    return response


def redirect_to_workspace(*, tab: str, case_id: str | None = None) -> ResponseReturnValue:
    values: dict[str, Any] = {
        'tab': tab,
        'domain': str(request.form.get('domain') or request.args.get('domain') or 'kubernetes'),
        'asset': str(request.form.get('asset') or request.args.get('asset') or 'all'),
    }
    if case_id:
        values['case'] = case_id
    return redirect(url_for('alert_intelligence.index', **values))
