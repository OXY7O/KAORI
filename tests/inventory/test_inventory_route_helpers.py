from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask

from app.inventory import routes
from app.inventory.routes import _inventory_cluster_scope, _inventory_template


@pytest.mark.parametrize(
    ('query_string', 'headers', 'expected_suffix'),
    [
        ('', {}, 'nodes/index.html'),
        (
            '?partial_mode=inventory_scope',
            {'HX-Request': 'true', 'HX-Target': 'nodes-inventory-scope'},
            'nodes/partials/_inventory_scope.html',
        ),
        (
            '?partial_mode=table_content',
            {'HX-Request': 'true', 'HX-Target': 'nodes-table-content'},
            'nodes/partials/_table_content.html',
        ),
        (
            '',
            {'HX-Request': 'true', 'HX-Target': 'nodes-inventory-card'},
            'nodes/partials/_table_card.html',
        ),
    ],
)
def test_inventory_template_selects_the_requested_htmx_boundary(
    query_string: str,
    headers: dict[str, str],
    expected_suffix: str,
) -> None:
    app = Flask(__name__)

    with app.test_request_context(f'/inventory/nodes{query_string}', headers=headers):
        assert _inventory_template('nodes').endswith(expected_suffix)


def test_inventory_cluster_scope_rejects_unknown_cluster_ids(monkeypatch) -> None:
    clusters = [SimpleNamespace(id='cluster-1'), SimpleNamespace(id='cluster-2')]
    monkeypatch.setattr(routes, 'get_inventory_clusters', lambda: clusters)

    assert _inventory_cluster_scope('cluster-2') == (clusters, 'cluster-2')
    assert _inventory_cluster_scope('missing') == (clusters, '')
    assert _inventory_cluster_scope('') == (clusters, '')
