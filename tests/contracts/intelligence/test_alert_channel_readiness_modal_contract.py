"""Read-only routing channel readiness, pagination, and modal isolation."""
from pathlib import Path

from flask import Flask
from werkzeug.datastructures import MultiDict

from app.intelligence.alert_intelligence import route_utils
from app.intelligence.alert_intelligence.service import build_channel_readiness

ROOT = Path(__file__).resolve().parents[3]


def channel_options(count: int = 12) -> list[dict]:
    return [
        {
            'name': f'Channel {i:02d}',
            'provider': 'Telegram',
            'icon': 'send',
            'status': 'Ready' if i % 2 == 0 else 'Retired',
            'eligible': i % 2 == 0,
            'registry_eligible': i % 4 == 0,
            'destination': 'must-not-be-rendered',
            'id': i,
        }
        for i in range(count)
    ]


def test_readiness_is_scoped_paginated_and_redacted() -> None:
    channels = channel_options()
    result = build_channel_readiness(channels, MultiDict(), domain='kubernetes')
    assert (result['total'], result['eligible'], result['unavailable']) == (12, 6, 6)
    assert result['pagination']['per_page'] == 5
    assert result['pagination']['total_pages'] == 3
    assert len(result['rows']) == 5
    assert set(result['rows'][0]) == {'name', 'provider', 'icon', 'status', 'eligible'}

    args = MultiDict({'channel_readiness': 'eligible', 'channel_page': '2', 'channel_q': 'telegram'})
    result = build_channel_readiness(channels, args, domain='kubernetes')
    assert [row['name'] for row in result['rows']] == ['Channel 10']
    assert result['pagination']['total_items'] == 6
    assert result['total'] == 12

    registry = build_channel_readiness(channels, args, domain='registry')
    assert registry['eligible'] == registry['pagination']['total_items'] == 3
    assert registry['pagination']['page'] == 1
    assert all(row['eligible'] for row in registry['rows'])

    empty = build_channel_readiness([], MultiDict({'channel_page': '999', 'channel_per_page': '999'}), domain='registry')
    assert empty['rows'] == []
    assert empty['pagination']['page'] == 1
    assert empty['pagination']['per_page'] == 5


def test_channel_modal_renders_only_page_and_keeps_parent_history() -> None:
    app = Flask(__name__, template_folder=str(ROOT / 'app/templates'))
    app.add_url_rule('/intelligence/alert-intelligence', 'alert_intelligence.index', lambda: '')
    args = MultiDict({'channel_readiness': 'eligible'})
    result = build_channel_readiness(channel_options(), args, domain='kubernetes')
    payload = {'channel_readiness': result, 'domain': 'kubernetes', 'domain_label': 'Kubernetes',
               'selected_asset_key': 'cluster-1'}
    with app.test_request_context('/intelligence/alert-intelligence?tab=routing'):
        html = app.jinja_env.get_template(
            'intelligence/partials/_alert_channel_readiness_dialog.html'
        ).render(payload=payload)
    assert 'data-kaori-native-dialog' in html
    assert 'alert-channel-readiness-registry' in html
    assert html.count('data-kaori-dialog-close') == 2
    assert 'hx-push-url="true"' not in html
    assert html.count('hx-push-url="false"') >= 4
    assert 'Channel 00' in html and 'Channel 08' in html
    assert 'Channel 10' not in html and 'Channel 01' not in html
    assert 'must-not-be-rendered' not in html
    assert 'channel_page=2' in html
    assert 'name="asset" value="cluster-1"' in html
    assert 'name="channel_per_page"' in html


def test_modal_refresh_returns_fragment_or_fails_closed(monkeypatch) -> None:
    app = Flask(__name__, template_folder=str(ROOT / 'app/templates'))
    app.add_url_rule('/intelligence/alert-intelligence', 'alert_intelligence.index', lambda: '')
    payload = {
        'tab': 'routing', 'domain': 'kubernetes', 'selected_asset_key': 'cluster-1',
        'channel_readiness': build_channel_readiness(channel_options(), MultiDict(), domain='kubernetes'),
    }
    monkeypatch.setattr(route_utils, 'get_alert_intelligence_payload', lambda args: payload)
    headers = {'HX-Request': 'true', 'HX-Target': 'alert-channel-readiness-registry'}
    with app.test_request_context('/intelligence/alert-intelligence?tab=routing', headers=headers):
        html = route_utils.index_response()
        assert isinstance(html, str)
        assert 'id="alert-channel-readiness-registry"' in html
        assert '<dialog' not in html
        assert 'Policy Registry' not in html

        payload['provider_case_mode'] = True
        response = route_utils.index_response()
        assert response.headers['HX-Redirect']
        payload['provider_case_mode'] = False
        payload['channel_readiness'] = None
        response = route_utils.index_response()
        assert response.headers['HX-Redirect']


def test_channel_readiness_registry_renders_zero_one_and_many_channels() -> None:
    app = Flask(__name__, template_folder=str(ROOT / 'app/templates'))
    app.add_url_rule('/intelligence/alert-intelligence', 'alert_intelligence.index', lambda: '')
    template = app.jinja_env.get_template('intelligence/partials/_alert_channel_readiness_registry.html')

    for count, expected_label in ((0, '0 Results'), (1, '1 Result'), (12, '12 Results')):
        readiness = build_channel_readiness(channel_options(count), MultiDict(), domain='kubernetes')
        payload = {
            'channel_readiness': readiness,
            'domain': 'kubernetes',
            'selected_asset_key': 'cluster-1',
        }
        with app.test_request_context('/intelligence/alert-intelligence?tab=routing'):
            html = template.render(payload=payload)
        assert expected_label in html
        assert 'id="alert-channel-readiness-registry"' in html
        assert 'name="channel_per_page"' in html
        if count == 0:
            assert 'No Notification Channels Configured' in html
        elif count == 12:
            assert 'channel_page=2' in html
