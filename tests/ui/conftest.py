from __future__ import annotations

import os
from collections.abc import Iterator
from threading import Thread
from unittest.mock import patch

import pytest
from playwright.sync_api import Page
from werkzeug.serving import make_server

from app import create_app
from app.access.authentication.readiness import AuthenticationDatabaseReadiness
from app.access.authentication.results import AuthResult
from app.extensions import login_manager
from app.models import User

CANONICAL_VIEWPORTS = {
    'large-desktop': (1440, 900),
    'laptop': (1280, 800),
    'compact-laptop': (1024, 768),
    'tablet': (768, 1024),
    'mobile': (390, 844),
    'small-mobile': (360, 800),
}

EMPTY_NAVIGATION_NOTIFICATIONS = {
    'items': [],
    'history_items': [],
    'attention_items': [],
    'active_jobs': [],
    'active_count': 0,
    'attention_count': 0,
    'unread_count': 0,
    'total_count': 0,
    'display_limit': 8,
    'job_display_limit': 6,
}

HIDDEN_CLUSTER_ONBOARDING = {
    'show_banner': False,
    'is_kubernetes_scope': False,
    'is_blocked': False,
    'has_clusters': False,
    'cluster_count': 0,
    'can_manage_clusters': True,
    'database_ready': True,
}


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if 'kaori_viewport' not in metafunc.fixturenames:
        return

    viewports = list(CANONICAL_VIEWPORTS.items())
    metafunc.parametrize('kaori_viewport', viewports, ids=[name for name, _ in viewports])


@pytest.fixture
def kaori_base_url() -> str:
    base_url = os.environ.get('KAORI_UI_BASE_URL', '').strip()
    if not base_url:
        pytest.skip('KAORI_UI_BASE_URL is required for browser-based UI validation')
    return base_url.rstrip('/')


@pytest.fixture
def configured_page(page: Page, kaori_viewport: tuple[str, tuple[int, int]]) -> Page:
    _, (width, height) = kaori_viewport
    page.set_viewport_size({'width': width, 'height': height})
    return page


@pytest.fixture(scope='module', params=('setup_required', 'database_unavailable'))
def kaori_unready_base_url(request: pytest.FixtureRequest) -> Iterator[tuple[str, str]]:
    state = str(request.param)
    if state == 'setup_required':
        readiness = AuthenticationDatabaseReadiness(
            ready=False,
            database_reachable=True,
            missing_tables=('roles', 'users'),
            detail='Authentication schema is incomplete for browser readiness testing.',
        )
    else:
        readiness = AuthenticationDatabaseReadiness(
            ready=False,
            database_reachable=False,
            detail='Authentication database is unavailable for browser readiness testing.',
        )

    app = create_app('testing')
    with patch(
        'app.access.authentication.routes.check_authentication_database_readiness',
        return_value=readiness,
    ):
        server = make_server('127.0.0.1', 0, app, threaded=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield state, f'http://127.0.0.1:{server.server_port}'
        finally:
            server.shutdown()
            thread.join(timeout=5)


@pytest.fixture(scope='module')
def kaori_authenticated_base_url() -> Iterator[str]:
    readiness = AuthenticationDatabaseReadiness(ready=True, database_reachable=True)
    user = User(
        id=1,
        username='browser-admin',
        email='browser-admin@example.invalid',
        display_name='Browser Admin',
        timezone='UTC',
        timezone_mode='manual',
        locale='en-US',
        date_format='day_month_year',
        time_format='24h',
        password_hash='',
        auth_session_version=1,
        auth_source='database',
        account_is_active=True,
        is_super_admin=True,
        last_auth_source='database',
        deleted_at=None,
    )
    app = create_app('testing')
    auth_result = AuthResult(True, 'success', source='database', user=user)

    with (
        patch(
            'app.access.authentication.routes.check_authentication_database_readiness',
            return_value=readiness,
        ),
        patch('app.access.authentication.routes.enabled_sso_providers', return_value=[]),
        patch('app.access.authentication.routes.authenticate', return_value=auth_result),
        patch('app.access.authentication.routes.record_successful_authentication', return_value=None),
        patch('app.access.authentication.routes._record_result', return_value=None),
        patch.object(login_manager, '_user_callback', lambda _user_id: user),
        patch(
            'app.bootstrap.presentation.get_navigation_notification_context',
            return_value=EMPTY_NAVIGATION_NOTIFICATIONS,
        ),
        patch('app.bootstrap.presentation.pop_operational_feedback', return_value=None),
        patch(
            'app.bootstrap.presentation.build_cluster_onboarding_context',
            return_value=HIDDEN_CLUSTER_ONBOARDING,
        ),
    ):
        server = make_server('127.0.0.1', 0, app, threaded=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}'
        finally:
            server.shutdown()
            thread.join(timeout=5)
