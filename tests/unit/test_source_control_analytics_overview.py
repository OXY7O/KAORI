"""Source Control Analytics must read only authorized committed evidence (#5126)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from jinja2 import Environment, FileSystemLoader
from werkzeug.exceptions import Forbidden, NotFound

from app.source_control import routes


def _authorized_scope() -> dict:
    return {
        'installations': (
            {
                'installation': SimpleNamespace(id=11),
                'connection': SimpleNamespace(name='Authorized GitHub App'),
                'committed': True,
                'last_committed_at': None,
            },
        ),
        'installation_count': 1,
        'committed_count': 1,
        'uncollected_count': 0,
        'latest_committed_at': None,
        'has_more': False,
    }


def test_analytics_denies_uat_actors_before_any_installation_read(monkeypatch):
    app = Flask(__name__)

    def deny():
        raise Forbidden()

    monkeypatch.setattr(routes, '_require_product_uat_access', deny)
    monkeypatch.setattr(
        routes,
        'build_source_control_overview',
        lambda: pytest.fail('Analytics read executed before UAT authorization'),
    )
    with app.test_request_context('/source-control/analytics?installation_id=11'):
        with pytest.raises(Forbidden):
            routes.analytics.__wrapped__()


@pytest.mark.parametrize('value', ['0', '-1', '１２', 'abc', '11OR1', '9' * 64, '12'])
def test_analytics_rejects_invalid_or_other_installation_before_repository_read(monkeypatch, value):
    app = Flask(__name__)
    monkeypatch.setattr(routes, '_require_product_uat_access', lambda: None)
    monkeypatch.setattr(routes, 'build_source_control_overview', _authorized_scope)
    monkeypatch.setattr(
        routes,
        'read_repository_coverage_for_current_session',
        lambda **_kwargs: pytest.fail('Unauthorized repository evidence read'),
    )
    with app.test_request_context('/source-control/analytics', query_string={'installation_id': value}):
        with pytest.raises(NotFound):
            routes.analytics.__wrapped__()


def test_analytics_reads_only_one_explicitly_selected_installation(monkeypatch):
    app = Flask(__name__)
    seen = []
    monkeypatch.setattr(routes, '_require_product_uat_access', lambda: None)
    monkeypatch.setattr(routes, 'build_source_control_overview', _authorized_scope)

    def read_coverage(*, authorized_installation_id):
        seen.append(authorized_installation_id)
        return SimpleNamespace(collected=True, grant_count=0, observed_count=0)

    monkeypatch.setattr(routes, 'read_repository_coverage_for_current_session', read_coverage)
    monkeypatch.setattr(routes, '_uncached_render', lambda name, **context: (name, context))
    with app.test_request_context('/source-control/analytics?installation_id=11'):
        template, context = routes.analytics.__wrapped__()
    assert template == 'source_control/analytics.html'
    assert context['selected_scope']
    assert context['selected_installation_id'] == 11
    assert context['repository_coverage'].grant_count == 0
    assert seen == [11]


def test_analytics_without_selected_installation_never_aggregates_repository_grants(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(routes, '_require_product_uat_access', lambda: None)
    monkeypatch.setattr(routes, 'build_source_control_overview', _authorized_scope)
    monkeypatch.setattr(
        routes,
        'read_repository_coverage_for_current_session',
        lambda **_kwargs: pytest.fail('Global grant aggregation must not occur'),
    )
    monkeypatch.setattr(routes, '_uncached_render', lambda name, **context: (name, context))
    with app.test_request_context('/source-control/analytics'):
        template, context = routes.analytics.__wrapped__()
    assert template == 'source_control/analytics.html'
    assert not context['selected_scope']
    assert context['repository_coverage'] is None


def test_analytics_reuses_shared_controls_and_never_claims_unqualified_evidence():
    root = Path(__file__).resolve().parents[2]
    template = (root / 'app/templates/source_control/analytics.html').read_text(encoding='utf-8')
    routes_text = (root / 'app/source_control/routes.py').read_text(encoding='utf-8')
    catalog = (root / 'app/common/workspace_navigation_catalog.py').read_text(encoding='utf-8')

    Environment(loader=FileSystemLoader(str(root / 'app/templates'))).parse(template)
    assert 'analytics/components/_controls_readiness.html' in template
    assert 'analytics_readiness.frame(' in template
    assert 'analytics_readiness.source_card(' in template
    for source in ('Domain Integration', 'Metrics Source', 'Alert Source'):
        assert source in template
    assert 'Not Evaluated' in template
    assert 'Not Collected' in template
    assert 'No committed Source Control metrics contract' in template
    assert 'No committed Source Control alert contract' in template
    assert 'repository_coverage.grant_count_matches_observation' in template
    assert 'repository_coverage.observed_count is not none' in template
    assert 'source_control/partials/_dashboard_repository_composition.html' in template
    assert 'source_control/partials/_dashboard_repository_lineage.html' in template
    assert 'source_control/partials/_dashboard_repository_attention.html' in template
    assert 'read_repository_coverage_for_current_session(' in routes_text
    assert "'source_control.analytics'" in catalog
    assert 'MetricsConsumer' not in template
    assert 'Prometheus' not in template
    assert '<script' not in template and '<style' not in template
