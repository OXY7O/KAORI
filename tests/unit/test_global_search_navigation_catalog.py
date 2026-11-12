from __future__ import annotations

from typing import Any

import pytest
from flask import Flask, url_for
from werkzeug.routing import BuildError

from app.platform_operations.global_search import service


def _sections() -> tuple[dict[str, Any], ...]:
    return (
        {
            'label': 'Main',
            'items': ({'key': 'welcome', 'label': 'Welcome', 'icon': 'sparkles', 'href': '/welcome', 'children': ()},),
        },
        {
            'label': 'Infrastructure',
            'items': (
                {
                    'key': 'artifact_registry',
                    'label': 'Artifact Registry',
                    'icon': 'package',
                    'children': (
                        {'key': 'overview', 'label': 'Overview', 'icon': 'layout-dashboard', 'href': '/registry'},
                        {'key': 'security', 'label': 'Security', 'icon': 'shield-check', 'href': '/registry/security'},
                    ),
                },
                {
                    'key': 'kubernetes',
                    'label': 'Kubernetes',
                    'icon': 'boxes',
                    'children': (
                        {'key': 'overview', 'label': 'Overview', 'icon': 'layout-dashboard', 'href': '/k8s'},
                        {'key': 'inventory', 'label': 'Inventory', 'icon': 'boxes', 'href': '/inventory/overview'},
                    ),
                },
            ),
        },
        {
            'label': 'Assurance',
            'items': (
                {
                    'key': 'security_posture',
                    'label': 'Security',
                    'icon': 'shield-alert',
                    'children': (
                        {'key': 'overview', 'label': 'Overview', 'icon': 'layout-dashboard', 'href': '/security'},
                    ),
                },
            ),
        },
    )


def test_quick_navigation_uses_current_authorized_workspaces_without_deep_views() -> None:
    entries = service._sidebar_navigation_results(query='', sidebar_sections=_sections())

    assert [item['title'] for item in entries] == [
        'Welcome',
        'Artifact Registry · Overview',
        'Kubernetes · Overview',
        'Security · Overview',
    ]
    assert len({item['url'] for item in entries}) == len(entries)
    assert all(item['kind'] == 'Navigation' for item in entries)


def test_capability_query_finds_recent_domains_and_security_views() -> None:
    entries = service._sidebar_navigation_results(query='security', sidebar_sections=_sections())

    assert {item['title'] for item in entries} == {
        'Artifact Registry · Security',
        'Security · Overview',
    }
    assert all(item['url'].startswith('/') for item in entries)


def test_search_does_not_synthesize_unauthorized_workspace_results() -> None:
    sections = _sections()
    only_welcome = ({'label': 'Main', 'items': sections[0]['items']},)
    assert service._sidebar_navigation_results(query='source control', sidebar_sections=only_welcome) == []
    assert service._sidebar_navigation_results(query='', sidebar_sections=only_welcome)[0]['title'] == 'Welcome'


def test_navigation_deduplicates_legacy_destinations_and_bounds_results(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        service,
        'url_for',
        lambda endpoint: '/inventory/overview' if endpoint == 'inventory.overview' else f'/{endpoint}',
    )
    results = service.navigation_results(
        query='inventory',
        has_permission=lambda permission: permission == 'inventory.view',
        sidebar_sections=_sections(),
    )

    assert sum(item['url'] == '/inventory/overview' for item in results) == 1
    assert len(results) <= service.MAX_NAVIGATION_RESULTS
    assert all('_score' in item for item in results)


def test_cve_navigation_targets_buildable_vulnerability_registry(monkeypatch: Any) -> None:
    app = Flask(__name__)
    app.add_url_rule(
        '/artifact-registry/security/vulnerabilities',
        endpoint='artifact_registry.security',
        view_func=lambda: 'ok',
    )
    app.add_url_rule(
        '/artifact-registry/security/cve/<string:cve_id>/impact',
        endpoint='artifact_registry.security_cve_impact',
        view_func=lambda cve_id: cve_id,
    )
    assert not any(entry.endpoint == 'artifact_registry.security_cve_impact' for entry in service.NAVIGATION_ENTRIES)
    vulnerability_entry = next(
        entry for entry in service.NAVIGATION_ENTRIES if entry.endpoint == 'artifact_registry.security'
    )
    monkeypatch.setattr(service, 'NAVIGATION_ENTRIES', (vulnerability_entry,))

    with app.test_request_context('/'):
        with pytest.raises(BuildError):
            url_for('artifact_registry.security_cve_impact')
        assert url_for('artifact_registry.security_cve_impact', cve_id='CVE-2022-1586').endswith(
            '/cve/CVE-2022-1586/impact'
        )
        for query in ('a', 'ar', 'art', 'cve', 'impact'):
            results = service.navigation_results(
                query=query,
                has_permission=lambda permission: permission == 'artifact_registry.view',
            )
            assert [result['url'] for result in results] == ['/artifact-registry/security/vulnerabilities']
            assert results[0]['title'] == 'Vulnerabilities'
        assert (
            service.navigation_results(query='cve', has_permission=lambda permission: False) == []
        )


def test_unbuildable_legacy_destination_is_logged_and_excluded(monkeypatch: Any, caplog: Any) -> None:
    app = Flask(__name__)
    app.add_url_rule(
        '/artifact-registry/security/vulnerabilities',
        endpoint='artifact_registry.security',
        view_func=lambda: 'ok',
    )
    app.add_url_rule(
        '/artifact-registry/security/cve/<string:cve_id>/impact',
        endpoint='artifact_registry.security_cve_impact',
        view_func=lambda cve_id: cve_id,
    )
    monkeypatch.setattr(
        service,
        'NAVIGATION_ENTRIES',
        (
            service.NavigationEntry(
                'CVE Impact',
                'Artifact Registry impact for an exact CVE',
                'artifact_registry.security_cve_impact',
                'shield-alert',
                'artifact_registry.view',
                ('cve',),
            ),
            service.NavigationEntry(
                'Vulnerabilities',
                'Artifact Registry vulnerabilities',
                'artifact_registry.security',
                'shield-alert',
                'artifact_registry.view',
                ('cve',),
            ),
        ),
    )
    with app.test_request_context('/'):
        results = service.navigation_results(
            query='cve',
            has_permission=lambda permission: permission == 'artifact_registry.view',
        )
    assert [result['title'] for result in results] == ['Vulnerabilities']
    assert [result['url'] for result in results] == ['/artifact-registry/security/vulnerabilities']
    assert 'Global Search skipped an unbuildable legacy navigation endpoint' in caplog.text
    assert 'artifact_registry.security_cve_impact' in caplog.text
