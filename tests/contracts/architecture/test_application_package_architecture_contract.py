from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / 'app'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_domain_first_application_package_architecture_is_release_locked() -> None:
    verifier = read('scripts/verify_application_package_architecture.py')
    quality_gate = read('scripts/quality_gate.sh')
    standard = read('docs/architecture/APPLICATION_PACKAGE_STANDARD.md')

    assert 'verify_application_package_architecture.py' in quality_gate
    assert 'domain-first MVC' in standard
    assert (
        'route -> form/contract -> service/policy -> repository/model or adapter -> presentation -> template'
        in standard
    )
    assert 'app/models/' in standard
    assert 'artifact_storage' in standard
    assert 'verify_application_package_architecture' not in verifier


def test_application_root_is_bounded_and_legacy_capability_roots_are_removed() -> None:
    allowed = {
        'access',
        'analytics',
        'artifact_storage',
        'bootstrap',
        'commands',
        'common',
        'config',
        'dashboards',
        'definitions',
        'extensions',
        'integrations',
        'intelligence',
        'kubernetes',
        'models',
        'platform_operations',
        'reports',
        'security',
        'settings',
        'static',
        'storage',
        'templates',
        'welcome',
    }
    actual = {path.name for path in APP.iterdir() if path.is_dir() and path.name != '__pycache__'}
    assert actual == allowed

    for legacy in (
        'auth',
        'users',
        'rbac',
        'identity_providers',
        'metrics_sources',
        'alert_sources',
        'object_storage',
        'notification_channels',
        'cluster',
        'governance',
        'kubernetes_operations',
        'jobs',
        'notifications',
        'retention',
        'knowledge',
        'resolver',
        'automation_control',
        'alert_intelligence',
    ):
        assert not (APP / legacy).exists(), legacy


def test_mvc_debt_is_explicit_and_cannot_become_an_unbounded_exception_bucket() -> None:
    baseline = json.loads(read('docs/architecture/mvc-debt-baseline.json'))
    route_debt = baseline['route_persistence_files']
    presentation_debt = baseline['presentation_mutation_files']

    assert route_debt == []
    assert presentation_debt == []
    assert len(route_debt) == len(set(route_debt))
    assert all((ROOT / path).exists() for path in (*route_debt, *presentation_debt))
