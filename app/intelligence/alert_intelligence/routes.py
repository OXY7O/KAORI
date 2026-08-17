from __future__ import annotations

from flask import Blueprint, render_template, request
from flask.typing import ResponseReturnValue

from app.access.rbac.decorators import permission_required
from app.intelligence.alert_intelligence.service import get_alert_intelligence_payload

alert_intelligence_bp = Blueprint(
    'alert_intelligence',
    __name__,
    url_prefix='/intelligence/alert-intelligence',
)


@alert_intelligence_bp.get('')
@permission_required('intelligence.view')
def index() -> ResponseReturnValue:
    payload = get_alert_intelligence_payload(request.args)
    if request.headers.get('HX-Request') == 'true':
        return render_template('intelligence/partials/_alert_intelligence_page.html', payload=payload)
    return render_template('intelligence/alert_intelligence.html', payload=payload)


@alert_intelligence_bp.get('/records')
@permission_required('intelligence.view')
def records() -> ResponseReturnValue:
    payload = get_alert_intelligence_payload(request.args)
    return render_template('intelligence/partials/_alert_intelligence_records.html', payload=payload)
