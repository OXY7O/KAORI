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

CANONICAL_VIEWPORTS = {
    'large-desktop': (1440, 900),
    'laptop': (1280, 800),
    'compact-laptop': (1024, 768),
    'tablet': (768, 1024),
    'mobile': (390, 844),
    'small-mobile': (360, 800),
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
