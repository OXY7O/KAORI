from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue

from app.intelligence.service import get_alert_intelligence_payload, get_recommendations_payload
from app.rbac.decorators import permission_required

intelligence_bp = Blueprint(
    'intelligence',
    __name__,
    url_prefix='/intelligence',
)


@intelligence_bp.route('/')
@permission_required('intelligence.view')
def index() -> ResponseReturnValue:
    return redirect(url_for('intelligence.recommendations'))


@intelligence_bp.route('/recommendations')
@permission_required('intelligence.view')
def recommendations() -> ResponseReturnValue:
    payload = get_recommendations_payload(
        request.args,
        page_mode='recommendations',
    )
    return render_template('intelligence/recommendations.html', payload=payload)


@intelligence_bp.route('/catalog')
@permission_required('intelligence.view')
def catalog() -> ResponseReturnValue:
    payload = get_recommendations_payload(
        request.args,
        page_mode='catalog',
    )
    return render_template('intelligence/recommendations.html', payload=payload)


@intelligence_bp.route('/alert-intelligence')
@permission_required('intelligence.view')
def alert_intelligence() -> ResponseReturnValue:
    payload = get_alert_intelligence_payload()
    return render_template('intelligence/alert_intelligence.html', payload=payload)
