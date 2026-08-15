from __future__ import annotations

from flask import Blueprint, abort, render_template, request
from flask.typing import ResponseReturnValue
from app.intelligence.overview import get_intelligence_overview_payload
from app.intelligence.service import (
    get_catalog_rule,
    get_recommendation_finding,
    get_recommendations_payload,
)
from app.rbac.decorators import permission_required

intelligence_bp = Blueprint(
    'intelligence',
    __name__,
    url_prefix='/intelligence',
)


@intelligence_bp.route('/')
@permission_required('intelligence.view')
def index() -> ResponseReturnValue:
    payload = get_intelligence_overview_payload()
    return render_template('intelligence/overview.html', payload=payload)


@intelligence_bp.route('/recommendations')
@permission_required('intelligence.view')
def recommendations() -> ResponseReturnValue:
    payload = get_recommendations_payload(
        request.args,
        page_mode='recommendations',
    )
    if request.headers.get('HX-Request') == 'true':
        target = (request.headers.get('HX-Target') or '').strip()
        template_name = (
            'intelligence/partials/_recommendations_results.html'
            if target == 'recommendations-results-content'
            else 'intelligence/partials/_recommendations_workspace.html'
        )
        return render_template(
            template_name,
            payload=payload,
            recommendation_summary_oob=True,
        )
    return render_template('intelligence/recommendations.html', payload=payload)


@intelligence_bp.get('/recommendations/<path:recommendation_key>/details')
@permission_required('intelligence.view')
def recommendation_details(recommendation_key: str) -> ResponseReturnValue:
    finding = get_recommendation_finding(recommendation_key)
    if finding is None:
        abort(404)
    return render_template(
        'intelligence/partials/_recommendation_detail_content.html',
        item=finding,
    )


@intelligence_bp.route('/catalog')
@permission_required('intelligence.view')
def catalog() -> ResponseReturnValue:
    payload = get_recommendations_payload(
        request.args,
        page_mode='catalog',
    )
    if request.headers.get('HX-Request') == 'true':
        target = (request.headers.get('HX-Target') or '').strip()
        template_name = (
            'intelligence/partials/_catalog_results.html'
            if target == 'catalog-results-content'
            else 'intelligence/partials/_catalog_workspace.html'
        )
        return render_template(template_name, payload=payload)
    return render_template('intelligence/rule_catalog.html', payload=payload)


@intelligence_bp.get('/catalog/<path:rule_key>/details')
@permission_required('intelligence.view')
def catalog_rule_details(rule_key: str) -> ResponseReturnValue:
    rule = get_catalog_rule(rule_key)
    if rule is None:
        abort(404)
    return render_template(
        'intelligence/partials/_catalog_detail_content.html',
        item=rule,
    )
