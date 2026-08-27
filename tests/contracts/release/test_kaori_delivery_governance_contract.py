from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
DESIGN = ROOT / 'docs/superpowers/specs/2026-08-27-kaori-agile-sdlc-governance-design.md'
WORKFLOW = ROOT / 'docs/engineering/KAORI_DELIVERY_WORKFLOW.md'
PROJECT_SETUP = ROOT / 'docs/engineering/KAORI_GITHUB_PROJECT_SETUP.md'
LABEL_CATALOG = ROOT / 'docs/engineering/KAORI_GITHUB_LABEL_CATALOG.md'
ISSUE_DIR = ROOT / '.github/ISSUE_TEMPLATE'
QUALITY_WORKFLOW = ROOT / '.github/workflows/quality.yml'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def load_form(name: str) -> dict:
    return yaml.safe_load((ISSUE_DIR / name).read_text(encoding='utf-8'))


def test_delivery_workflow_locks_branch_and_uat_authority() -> None:
    source = read(WORKFLOW)
    assert 'Governance Version: 1.0' in source
    assert 'Only two branches are long-lived by default' in source
    assert 'main' in source
    assert 'kaori/staging' in source
    assert 'kaori/working' in source
    assert 'retired' in source.casefold()
    assert 'two-week' in source
    assert 'Iteration' in source
    assert 'Milestone' in source
    assert 'Local UAT' in source
    assert 'merge commit' in source.casefold()
    assert 'Done' in source


def test_design_and_workflow_allow_only_two_default_long_lived_branches() -> None:
    design = read(DESIGN)
    workflow = read(WORKFLOW)
    assert 'Only two branches are long-lived by default' in design
    assert 'Only two branches are long-lived by default' in workflow


def test_issue_forms_cover_primary_governed_types() -> None:
    expected = {
        'epic.yml': ('Epic', '[EPIC] '),
        'user-story.yml': ('User Story', '[STORY] '),
        'bug.yml': ('Bug', '[BUG] '),
        'task.yml': ('Task', '[TASK] '),
        'spike.yml': ('Spike', '[SPIKE] '),
    }
    for filename, (name, prefix) in expected.items():
        form = load_form(filename)
        assert form['name'] == name
        assert form['title'] == prefix
        assert form['body']


def test_blank_issue_creation_is_disabled() -> None:
    config = load_form('config.yml')
    assert config['blank_issues_enabled'] is False


def test_pull_request_template_requires_delivery_evidence() -> None:
    source = read(ROOT / '.github/PULL_REQUEST_TEMPLATE.md')
    for token in (
        'Linked Issue',
        'Acceptance Criteria Coverage',
        'Test Evidence',
        'Security Impact',
        'Migration / Data Impact',
        'Observability / Operational Impact',
        'UAT',
        'Release Impact',
    ):
        assert token in source


def test_project_setup_guide_defines_canonical_fields_and_views() -> None:
    source = read(PROJECT_SETUP)
    for token in (
        'Backlog',
        'Refinement',
        'Ready',
        'In Progress',
        'Code Review / CI',
        'Staging',
        'UAT',
        'Blocked',
        'Done',
        'P0 — Critical',
        'P1 — High',
        'P2 — Medium',
        'P3 — Low',
        '1, 2, 3, 5, 8, 13',
        'Product Backlog',
        'Current Sprint',
        'Staging & UAT',
        'Release Readiness',
    ):
        assert token in source


def test_label_catalog_uses_portable_metadata_without_status_duplication() -> None:
    source = read(LABEL_CATALOG)
    for token in (
        'type:epic',
        'type:story',
        'type:bug',
        'type:task',
        'type:spike',
        'type:chore',
        'type:tech-debt',
        'priority:p0-critical',
        'area:backend',
        'area:ci-cd',
        'impact:security',
        'workflow:blocked',
        'workflow:expedite',
    ):
        assert token in source
    assert 'status:done' not in source
    assert 'status:in-progress' not in source


def test_full_ci_runs_for_governed_kaori_branches_and_staging_prs() -> None:
    source = read(QUALITY_WORKFLOW)
    assert '- "kaori/**"' in source
    assert '- kaori/staging' in source
    assert '- kaori/working' not in source
