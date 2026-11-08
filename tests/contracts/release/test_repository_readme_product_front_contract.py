from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
README = ROOT / 'README.md'


def test_repository_readme_front_explains_the_product_and_capabilities() -> None:
    source = README.read_text(encoding='utf-8')

    for token in (
        'Knowledge, Automation, Operations, Resilience & Intelligence',
        'Kubernetes',
        'Object Storage',
        'Analytics',
        'Reports',
        'Intelligence',
        'Governance',
        'Prometheus',
        'Alertmanager',
        '## Architecture',
        '## Quick Start',
        '## Deployment & Release',
        '## Documentation',
    ):
        assert token in source


def test_repository_readme_keeps_release_claims_inside_governed_boundaries() -> None:
    source = README.read_text(encoding='utf-8')

    assert 'kaori/staging' in source
    assert 'immutable' in source.lower()
    assert 'explicit UAT acceptance' in source
    assert 'stable' in source.lower()
    assert 'latest' not in source.lower()


def test_canonical_product_direction_keeps_dual_delivery_as_unreleased_roadmap() -> None:
    source = (ROOT / 'docs/product/README.md').read_text(encoding='utf-8')
    license_text = (ROOT / 'LICENSE').read_text(encoding='utf-8')

    assert '## 2. Delivery Models and Roadmap Maturity' in source
    for model in (
        'Customer-managed self-hosted KAORI — Planned',
        'OXY7O-managed subscription KAORI — Planned for dedicated customer',
        'Multi-organization subscription SaaS — Future',
    ):
        assert model in source
    for boundary in (
        'one capability- and domain-first product',
        'Kubernetes Tenant',
        'not** a SaaS customer organization',
        'do not establish multi-customer isolation',
        'Phase 0 architecture',
        '#4184',
        '#4185',
        'app.kaori.cloud',
        'separately accepted release evidence',
    ):
        assert boundary in source
    assert 'external\ndistribution, sale or third-party SaaS' in source
    assert 'prior written authorization' in license_text
    assert 'commercially\navailable offerings' in source
