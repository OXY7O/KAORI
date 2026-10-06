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
