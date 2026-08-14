from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

HERO_EXPECTATIONS = {
    'overview': (
        'Review committed Kubernetes assets and fleet inventory signals.',
        'Fleet Posture',
    ),
    'nodes': (
        'Review node readiness, capacity, runtime, and scheduling evidence.',
        'Node Readiness',
    ),
    'namespaces': (
        'Review namespace lifecycle, controls, security, and object composition.',
        'Lifecycle Posture',
    ),
    'workloads': (
        'Review workload state, delivery, placement, and Pod template evidence.',
        'Runtime Posture',
    ),
    'pods': (
        'Review Pod readiness, placement, ownership, and container runtime evidence.',
        'Runtime Posture',
    ),
    'services': (
        'Review Service access, ports, backend registration, and selected Pods.',
        'Backend Registration',
    ),
    'ingresses': (
        'Review Ingress publication, TLS references, routes, and backend Services.',
        'Routing Posture',
    ),
    'storage': (
        'Review storage provisioning, capacity, access, binding, and lifecycle evidence.',
        'Storage Lifecycle',
    ),
    'configuration': (
        'Review ConfigMap and Secret keys, mutation, collection, and Pod references.',
        'Protected Metadata',
    ),
    'topology': (
        'Explore ownership, placement, and dependencies from committed inventory.',
        'Graph Coverage',
    ),
}


def _read(resource: str) -> str:
    return (ROOT / 'app' / 'templates' / 'inventory' / 'kubernetes' / resource / 'partials' / '_hero.html').read_text(encoding='utf-8')


def _normalized(source: str) -> str:
    return re.sub(r'\s+', ' ', source)


def test_inventory_hero_descriptions_follow_the_compact_copy_budget() -> None:
    for resource, (description, _context_title) in HERO_EXPECTATIONS.items():
        source = _normalized(_read(resource))
        assert description in source, resource
        assert 7 <= len(description.rstrip('.').split()) <= 12, resource
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
    styling_guide = (ROOT / 'docs/design/KAORI_STYLING_GUIDE.md').read_text(encoding='utf-8')

    for source in (hero_contract, styling_guide):
        assert 'description target: 7–12 words' in source
        assert 'right-panel title' in source
        assert 'metric helper: optional' in source
