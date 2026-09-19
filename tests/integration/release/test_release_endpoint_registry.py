from __future__ import annotations

import sys
from pathlib import Path

from app import create_app

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from release_surface_registry import RUNTIME_ENDPOINTS, navigation_endpoints  # noqa: E402


def test_release_navigation_and_system_endpoints_are_registered() -> None:
    app = create_app('testing')
    registered = {rule.endpoint for rule in app.url_map.iter_rules()}
    expected = set(navigation_endpoints()) | set(RUNTIME_ENDPOINTS)

    assert expected <= registered, f'Missing release endpoints: {sorted(expected - registered)}'
    assert 'cluster.list_clusters' not in registered
