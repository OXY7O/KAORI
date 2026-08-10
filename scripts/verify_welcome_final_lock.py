#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_HERO_DESCRIPTION = (
    'Operate and govern infrastructure with unified visibility, workflows, analytics, reporting, and administration.'
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    template = read('app/templates/welcome/index.html')
    shortcuts = read('app/welcome/shortcuts.py')
    contract = read('tests/contracts/welcome/test_welcome_navigation_contract.py')

    # Locked visual composition: shared KAORI components remain authoritative.
    require('components/page_hero.html' in template, 'Welcome must use the shared page hero.', errors)
    require(
        'components/welcome_capability_group.html' in template,
        'Welcome must use the shared capability group component.',
        errors,
    )
    require(
        'components/workspace_link_card.html' in template,
        'Welcome must use the shared workspace link card component.',
        errors,
    )
    require(
        EXPECTED_HERO_DESCRIPTION in ' '.join(template.split()),
        'Welcome hero description does not match the locked concise copy.',
        errors,
    )

    # K8s Governance copy refinement must remain metadata-only.
    governance_start = shortcuts.find("'title': 'K8s Governance'")
    reports_start = shortcuts.find("'title': 'Reports'", governance_start)
    require(governance_start >= 0, 'K8s Governance shortcut is missing.', errors)
    require(reports_start > governance_start, 'Unable to isolate K8s Governance shortcut block.', errors)

    if governance_start >= 0 and reports_start > governance_start:
        governance = shortcuts[governance_start:reports_start]
        require("'scope': 'Compute'" in governance, 'K8s Governance scope must be Compute.', errors)
        require(
            "('governance.view', 'governance.overview')" in governance,
            'K8s Governance overview permission/endpoint contract changed.',
            errors,
        )
        require(
            "('tls_certificates.view', 'governance.tls_certificates')" in governance,
            'K8s Governance TLS permission/endpoint contract changed.',
            errors,
        )
        require(
            "'group': 'assurance'" in governance,
            'K8s Governance must remain in the Governance & Reporting capability group.',
            errors,
        )

    # Cross-domain remains intentional for genuinely multi-domain workspaces.
    intelligence_start = shortcuts.find("'title': 'Intelligence'")
    integrations_start = shortcuts.find("'title': 'Integrations'", intelligence_start)
    if intelligence_start >= 0 and integrations_start > intelligence_start:
        intelligence = shortcuts[intelligence_start:integrations_start]
        require(
            "'scope': 'Cross-domain'" in intelligence,
            'Intelligence must retain the Cross-domain scope.',
            errors,
        )

    reports_start = shortcuts.find("'title': 'Reports'")
    access_start = shortcuts.find("'title': 'Access'", reports_start)
    if reports_start >= 0 and access_start > reports_start:
        reports = shortcuts[reports_start:access_start]
        require(
            "'scope': 'Cross-domain'" in reports,
            'Reports must retain the Cross-domain scope.',
            errors,
        )

    # Existing navigation contract remains part of the release boundary.
    require(
        'test_welcome_catalog_matches_current_primary_navigation_domains' in contract,
        'Welcome navigation contract test is missing.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Welcome final-lock validation passed: concise hero copy, Compute-scoped '
        'K8s Governance metadata, canonical components, and navigation contracts are intact.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
