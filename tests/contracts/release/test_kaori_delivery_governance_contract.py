from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / 'docs/engineering/KAORI_DELIVERY_WORKFLOW.md'
ISSUE_DIR = ROOT / '.github/ISSUE_TEMPLATE'
QUALITY_WORKFLOW = ROOT / '.github/workflows/quality.yml'
PR_TEMPLATE = ROOT / '.github/PULL_REQUEST_TEMPLATE.md'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def load_form(name: str) -> dict:
    return yaml.safe_load((ISSUE_DIR / name).read_text(encoding='utf-8'))


def test_delivery_workflow_locks_current_lifecycle_branch_and_uat_authority() -> None:
    source = read(WORKFLOW)
    for token in (
        'Governance Version: 1.0',
        'Inbox',
        'Backlog',
        'Ready',
        'In Progress',
        'Review',
        'UAT',
        'Done',
        'Only two branches are long-lived by default',
        'main',
        'kaori/staging',
        'kaori/working',
        'Local UAT',
        'merge commit',
    ):
        assert token in source


def test_issue_forms_use_native_issue_type_without_title_prefixes() -> None:
    expected = {
        'epic.yml': 'Epic',
        'user-story.yml': 'User Story',
        'bug.yml': 'Bug',
        'task.yml': 'Task',
        'spike.yml': 'Spike',
    }
    for filename, name in expected.items():
        form = load_form(filename)
        assert form['name'] == name
        assert form['title'] == ''
        assert form['body']
        markdown = '\n'.join(
            item.get('attributes', {}).get('value', '') for item in form['body'] if item.get('type') == 'markdown'
        )
        assert 'Native GitHub Issue Type' in markdown


def test_blank_issue_creation_is_disabled() -> None:
    config = load_form('config.yml')
    assert config['blank_issues_enabled'] is False


def test_pull_request_template_requires_governed_delivery_evidence() -> None:
    source = read(PR_TEMPLATE)
    for token in (
        'Linked Work',
        'Why',
        'What Changed',
        'Out of Scope',
        'Acceptance Criteria Coverage',
        'Verification Evidence',
        'Security Impact',
        'Migration / Data Impact',
        'Observability / Operational Impact',
        'UAT',
        'Release Impact',
    ):
        assert token in source
    assert 'Refs #<issue>' in source
    assert 'Closes #<issue>' in source


def test_full_ci_runs_for_governed_kaori_branches_and_staging_prs() -> None:
    source = read(QUALITY_WORKFLOW)
    assert '- "kaori/**"' in source
    assert '- kaori/staging' in source
    assert '- kaori/working' not in source
