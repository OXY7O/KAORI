from __future__ import annotations

import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MINIMUM_HERO_DESCRIPTION = 'Review cluster health, capacity, alerts, and readiness.'
PREFERRED_HERO_DESCRIPTION = (
    'Review report execution, artifact readiness, storage availability, and retained lifecycle state.'
)


def test_server_deployment_boundary_is_repository_canonical() -> None:
    assert (ROOT / 'deploy' / 'server').is_dir()
    assert not (ROOT / 'deploy' / 'vps').exists()

    workflow = (ROOT / '.github' / 'workflows' / 'deploy-staging-host.yml').read_text(encoding='utf-8')
    assert 'deploy/server' in workflow
    assert 'deploy/vps' not in workflow
    assert 'compose.server.yml' in (ROOT / 'deploy' / 'server' / 'deploy.sh').read_text(encoding='utf-8')

    edge = (ROOT / 'example' / 'shared-edge' / 'verify.sh').read_text(encoding='utf-8')
    assert 'deploy/vps' not in edge
    assert 'compose.yml' in edge
    assert 'EDGE_SITES_DIR' in edge
    assert 'edge-public' not in workflow
    assert 'deploy/nginx' not in workflow
    assert 'example/shared-edge' not in workflow


def test_example_boundary_contains_kaori_laptop_runtime_not_runner() -> None:
    example_root = ROOT / 'example'
    assert not (example_root / 'runner').exists()

    kaori_root = example_root / 'kaori'
    for relative in ('compose.yml', '.env.example', 'run.sh', 'README.md'):
        assert (kaori_root / relative).is_file(), f'missing laptop runtime example: {relative}'

    script = (kaori_root / 'run.sh').read_text(encoding='utf-8')
    for action in ('start', 'status', 'logs', 'stop', 'reset'):
        assert action in script


def test_repository_front_uses_stable_professional_badges_and_global_architecture() -> None:
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')

    for badge_label in ('CI', 'Version', 'Python', 'License'):
        assert f'alt="{badge_label}"' in readme
    assert 'img.shields.io/github/v/release' not in readme
    assert 'Disposable GitHub Actions Runner' not in readme
    assert 'example/kaori' in readme
    assert 'Platform Capabilities' in readme


def test_hero_v17_accepts_uat_description_contract_and_rejects_shorter_copy() -> None:
    namespace = runpy.run_path(str(ROOT / 'scripts' / 'verify_hero_component_standard.py'))
    validate = namespace['_validate_description_budget']

    validate(MINIMUM_HERO_DESCRIPTION, owner='minimum-reference')
    validate(PREFERRED_HERO_DESCRIPTION, owner='preferred-reference')

    with pytest.raises(AssertionError, match='7-15 words'):
        validate('Review cluster health, capacity, and readiness.', owner='too-short')


def test_hero_v17_operational_metadata_state_contract_is_executable() -> None:
    namespace = runpy.run_path(str(ROOT / 'scripts' / 'verify_hero_component_standard.py'))
    verify_state_contract = namespace.get('_verify_operational_metadata_state_contract')
    assert callable(verify_state_contract)
    verify_state_contract()

    standard = (ROOT / 'docs' / 'design' / 'components' / 'HERO.md').read_text(encoding='utf-8')
    assert '# KAORI Hero Component Standard v1.8' in standard
    assert 'normal, blocked, and degraded' in standard
    assert 'Blocked may use reduced readiness metadata' not in standard

    storage_hero = (
        ROOT / 'app' / 'templates' / 'kubernetes' / 'analytics' / 'storage' / 'partials' / '_hero.html'
    ).read_text(encoding='utf-8')
    assert 'page_hero.analytics_metadata(' in storage_hero


def test_cluster_readiness_uses_cluster_integrations_vocabulary() -> None:
    source = (ROOT / 'app' / 'common' / 'dependencies.py').read_text(encoding='utf-8')
    start = source.index('def cluster_required_blocker()')
    end = source.index('\n\ndef metrics_source_setup_blocker', start)
    blocker = source[start:end]

    assert "'action_label': 'Open Cluster Integrations'" in blocker
    assert "'action_url': url_for('integrations.kubernetes')" in blocker
    assert "'permission': 'clusters.manage'" in blocker
    assert "'action_label': 'Open Cluster Integration'" not in blocker
    assert "'action_label': 'Open Orchestration Integration'" not in blocker
