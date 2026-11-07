from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
DEPENDABOT = ROOT / '.github/dependabot.yml'
DEVELOPER_CHECK = ROOT / '.github/workflows/developer-check.yml'


def test_dependabot_version_update_intake_is_bounded_to_governed_staging() -> None:
    settings = yaml.safe_load(DEPENDABOT.read_text(encoding='utf-8'))
    assert settings['version'] == 2

    ecosystems = {item['package-ecosystem']: item for item in settings['updates']}
    assert set(ecosystems) == {'pip', 'npm', 'github-actions'}
    assert ecosystems['pip']['directory'] == '/requirements'
    assert ecosystems['npm']['directory'] == '/'
    assert ecosystems['github-actions']['directory'] == '/'

    for item in ecosystems.values():
        assert item['target-branch'] == 'kaori/staging'
        assert item['schedule'] == {
            'interval': 'weekly',
            'day': 'monday',
            'time': '04:00',
            'timezone': 'Asia/Jakarta',
        }
        assert item['open-pull-requests-limit'] == 2
        assert item['assignees'] == ['lethisa']
        assert set(item['labels']) == {'area:platform', 'scope:ci'}
        assert len(item['groups']) == 1
        group = next(iter(item['groups'].values()))
        assert group['patterns'] == ['*']
        assert set(group['update-types']) == {'minor', 'patch'}
        assert 'allow' not in item
        assert 'registries' not in item
        assert 'ignore' not in item

    source = DEPENDABOT.read_text(encoding='utf-8').lower()
    assert 'auto-merge' not in source
    assert 'automerge' not in source


def test_dependabot_branches_do_not_bypass_canonical_developer_check() -> None:
    workflow = yaml.safe_load(DEVELOPER_CHECK.read_text(encoding='utf-8'))
    route = workflow['jobs']['route']
    assert "startsWith(github.event.pull_request.head.ref, 'kaori/')" in route['if']
    assert 'github.event.pull_request.head.repo.full_name == github.repository' in route['if']
    full_admission = workflow['jobs']['full-admission']
    assert "needs.developer-check.result == 'success'" in full_admission['if']
    assert 'github.event.pull_request.head.repo.full_name == github.repository' in full_admission['if']
