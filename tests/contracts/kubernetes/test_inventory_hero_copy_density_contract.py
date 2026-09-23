from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

HERO_EXPECTATIONS = {
    'overview': (
        'Review Kubernetes inventory coverage, assets, and fleet signals.',
        'Fleet Posture',
    ),
    'nodes': (
        'Review node readiness, capacity, scheduling, and platform posture.',
        'Node Readiness',
    ),
    'namespaces': (
        'Review namespaces, lifecycle, security, and workload composition.',
        'Lifecycle Posture',
    ),
    'workloads': (
        'Review workloads, runtime state, replicas, strategy, and placement.',
        'Runtime Posture',
    ),
    'pods': (
        'Review Pods, readiness, placement, ownership, and conditions.',
        'Runtime Posture',
    ),
    'services': (
        'Review Services, exposure, ports, selectors, and endpoints.',
        'Backend Registration',
    ),
    'ingresses': (
        'Review Ingress routes, hosts, TLS, backends, and routing posture.',
        'Routing Posture',
    ),
    'storage': (
        'Review storage assets, capacity, bindings, access, and lifecycle.',
        'Storage Lifecycle',
    ),
    'configuration': (
        'Review ConfigMaps, Secrets, references, and mutation evidence.',
        'Protected Metadata',
    ),
    'topology': (
        'Explore Kubernetes ownership, placement, links, and dependencies.',
        'Graph Coverage',
    ),
}


def _read(resource: str) -> str:
    return (ROOT / 'app' / 'templates' / 'kubernetes' / 'inventory' / resource / 'partials' / '_hero.html').read_text(
        encoding='utf-8'
    )


def _normalized(source: str) -> str:
    return re.sub(r'\s+', ' ', source)


def test_inventory_hero_descriptions_follow_the_compact_copy_budget() -> None:
    for resource, (description, _context_title) in HERO_EXPECTATIONS.items():
        source = _normalized(_read(resource))
        assert description in source, resource
        assert 7 <= len(re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*", description)) <= 15, resource
        assert len(description) <= 68, resource
        assert 'from committed Kubernetes inventory snapshots' not in source, resource


def test_inventory_hero_context_panels_use_short_titles_and_concise_helpers() -> None:
    literal_helpers = re.compile(r"\(\s*'[^']+'\s*,\s*'[^']+'\s*,[^\n]+,\s*'([^']+)'")
    for resource, (_description, context_title) in HERO_EXPECTATIONS.items():
        source = _read(resource)
        assert context_title in source, resource
        assert len(context_title.replace('&', '').split()) <= 4, resource

        if resource == 'topology':
            assert source.count('context_metric_helper_classes()') == 2
            assert 'Mapped dependencies' in source
            assert 'Graph limit omitted' in source
            continue

        helpers = literal_helpers.findall(source)
        assert len(helpers) >= 2, resource
        assert all(1 <= len(helper.split()) <= 4 for helper in helpers[:2]), resource


def test_inventory_hero_copy_budget_is_documented() -> None:
    hero_contract = (ROOT / 'docs/design/components/HERO.md').read_text(encoding='utf-8')

    assert '# KAORI Hero Component Standard v1.8' in hero_contract
    assert '7–15 words' in hero_contract
    assert '8–12 words' in hero_contract
    assert 'maximum 68 characters' in hero_contract
    assert 'action-oriented' in hero_contract
    assert 'right-panel title' in hero_contract
    assert 'metric helper: optional' in hero_contract
