"""Fail-closed same-head Draft -> Ready Developer Check reuse (#2220)."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
POLICY = ROOT / 'scripts/ci_admission_policy.py'
WORKFLOW = ROOT / '.github/workflows/developer-check.yml'
REPO = 'OXY7O/KAORI'
HEAD = 'a' * 40
BASE = 'b' * 40
TREE = 'c' * 40
PLAN = (
    'python=false templates=true frontend=false migrations=false contracts=true '
    'reports=false wide=false template_scope=changed capabilities=settings '
    'tests=tests/contracts/settings tests/settings'
)


def load_policy() -> ModuleType:
    spec = importlib.util.spec_from_file_location('kaori_draft_evidence_policy', POLICY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def proven_case():
    policy = load_policy()
    timestamp = datetime.now(UTC)
    evidence = policy.build_draft_developer_evidence(
        repository=REPO,
        pull_number=2220,
        head_sha=HEAD,
        base_sha=BASE,
        source_tree=TREE,
        plan=PLAN,
        run_id=707,
        run_attempt=1,
        workflow_ref=f'{REPO}/.github/workflows/developer-check.yml@refs/pull/2220/merge',
        authority_fingerprint='fingerprint',
        toolchain_key='toolchain',
        created_at=timestamp.isoformat(),
    )
    run = {
        'id': 707,
        'run_attempt': 1,
        'status': 'completed',
        'conclusion': 'success',
        'event': 'pull_request',
        'path': '.github/workflows/developer-check.yml',
        'head_sha': HEAD,
        'head_branch': 'kaori/perf-2220-exact-draft-evidence-reuse',
        'head_repository': {'full_name': REPO},
        'pull_requests': [
            {
                'number': 2220,
                'head': {'sha': HEAD, 'ref': 'kaori/perf-2220-exact-draft-evidence-reuse'},
                'base': {'sha': BASE},
            }
        ],
    }
    jobs = [
        {'name': name, 'status': 'completed', 'conclusion': outcome}
        for name, outcome in policy._required_developer_jobs(PLAN).items()
    ]
    args = dict(
        repository=REPO,
        pull_number=2220,
        head_sha=HEAD,
        base_sha=BASE,
        source_tree=TREE,
        plan=PLAN,
        authority_fingerprint='fingerprint',
        toolchain_key='toolchain',
        current_run_id=708,
        head_ref='kaori/perf-2220-exact-draft-evidence-reuse',
        current_time=timestamp,
    )
    return policy, evidence, run, jobs, args


def test_exact_completed_draft_plan_uses_audited_proof_not_sha_alone() -> None:
    policy, evidence, run, jobs, args = proven_case()
    decision = policy.draft_developer_reuse_decision(evidence, run, jobs, **args)
    assert decision.reusable is True
    assert 'all jobs' in decision.reason


@pytest.mark.parametrize(
    'field,value',
    [
        ('repository', 'another/repo'),
        ('pull_number', 2221),
        ('head_sha', 'd' * 40),
        ('base_sha', 'e' * 40),
        ('source_tree', 'f' * 40),
        ('plan', 'python=true tests=none'),
        ('authority_fingerprint', 'different'),
        ('toolchain_key', 'different'),
    ],
)
def test_any_identity_or_validation_authority_drift_fails_closed(field: str, value: object) -> None:
    policy, evidence, run, jobs, args = proven_case()
    args[field] = value
    assert not policy.draft_developer_reuse_decision(evidence, run, jobs, **args).reusable


@pytest.mark.parametrize(
    'field,value',
    [
        ('status', 'in_progress'),
        ('conclusion', 'failure'),
        ('event', 'push'),
        ('head_sha', 'another-head'),
        ('head_repository', {'full_name': 'untrusted/fork'}),
        ('path', '.github/workflows/quality.yml'),
        ('run_attempt', 2),
    ],
)
def test_untrusted_incomplete_or_rerun_workflow_fails_closed(field: str, value: object) -> None:
    policy, evidence, run, jobs, args = proven_case()
    run[field] = value
    assert not policy.draft_developer_reuse_decision(evidence, run, jobs, **args).reusable


@pytest.mark.parametrize(
    'name',
    [
        'Route Checks',
        'Prepare Toolchain',
        'Frontend & Focused Validation',
        'Developer Check',
    ],
)
def test_failed_or_missing_mandatory_draft_jobs_never_reuse(name: str) -> None:
    policy, evidence, run, jobs, args = proven_case()
    changed = [dict(job, conclusion='failure') if job['name'] == name else job for job in jobs]
    assert not policy.draft_developer_reuse_decision(evidence, run, changed, **args).reusable
    missing = [job for job in jobs if job['name'] != name]
    assert not policy.draft_developer_reuse_decision(evidence, run, missing, **args).reusable


def test_other_pr_or_head_branch_linkage_rejects_reuse() -> None:
    policy, evidence, run, jobs, args = proven_case()
    args['head_ref'] = 'kaori/different-branch'
    assert not policy.draft_developer_reuse_decision(evidence, run, jobs, **args).reusable
    args['head_ref'] = 'kaori/perf-2220-exact-draft-evidence-reuse'
    run['pull_requests'] = []
    assert not policy.draft_developer_reuse_decision(evidence, run, jobs, **args).reusable
    run['pull_requests'] = [{'number': 2221, 'head': {'sha': HEAD}, 'base': {'sha': BASE}}]
    assert not policy.draft_developer_reuse_decision(evidence, run, jobs, **args).reusable


def test_duplicate_extra_cancelled_and_stale_draft_results_fail_closed() -> None:
    policy, evidence, run, jobs, args = proven_case()
    assert not policy.draft_developer_reuse_decision(evidence, run, jobs + [jobs[0]], **args).reusable
    assert not policy.draft_developer_reuse_decision(
        evidence, run, [dict(job, status='cancelled') for job in jobs], **args
    ).reusable
    args['current_time'] += timedelta(hours=3)
    assert not policy.draft_developer_reuse_decision(evidence, run, jobs, **args).reusable


def test_reuse_proof_respects_python_only_and_docs_only_lane_selection() -> None:
    policy = load_policy()
    docs = (
        'python=false templates=false frontend=false migrations=false contracts=false '
        'reports=false wide=false template_scope=none capabilities=shared tests=none'
    )
    python = (
        'python=true templates=false frontend=false migrations=false contracts=false '
        'reports=false wide=false template_scope=none capabilities=shared tests=none'
    )
    assert policy._required_developer_jobs(docs) == {
        'Route Checks': 'success',
        'Prepare Toolchain': 'skipped',
        'Python & Governance': 'skipped',
        'Frontend & Focused Validation': 'skipped',
        'Developer Check': 'success',
        'Full Admission': 'skipped',
    }
    assert policy._required_developer_jobs(python)['Python & Governance'] == 'success'
    assert policy._required_developer_jobs(python)['Frontend & Focused Validation'] == 'skipped'
    with pytest.raises(ValueError):
        policy._required_developer_jobs('unsafe/incomplete plan')


def test_ready_integration_preserves_exact_head_aggregate_and_full_admission() -> None:
    source = WORKFLOW.read_text(encoding='utf-8')
    workflow = yaml.safe_load(source)
    jobs = workflow['jobs']
    assert set(jobs) == {
        'route',
        'toolchain',
        'python-check',
        'validation-check',
        'developer-check',
        'full-admission',
        'ready-admission-guard',
    }
    assert "needs.route.outputs.reuse != 'true'" in jobs['toolchain']['if']
    assert "needs.route.outputs.reuse != 'true'" in jobs['python-check']['if']
    assert "needs.route.outputs.reuse != 'true'" in jobs['validation-check']['if']
    assert "needs.developer-check.result == 'success'" in jobs['full-admission']['if']
    # GitHub implicitly adds success() to job conditionals without a status
    # function. Heavy lanes are deliberately skipped on verified reuse; Ready
    # Full Admission must not be accidentally skipped with them.
    assert '!cancelled()' in jobs['full-admission']['if']
    assert 'github.event.pull_request.draft == false' in jobs['full-admission']['if']
    assert 'github.event.pull_request.head.repo.full_name == github.repository' in jobs['full-admission']['if']
    assert 'VERIFIED_DRAFT_REUSE:' in source
    assert 'assert_lane' in source and 'Ready admission denied' in source
    assert 'Upload Draft Route Identity' in source
    assert 'if-no-files-found: error' in source
    assert 'find-draft-developer-evidence' in source
    assert 'github.event.pull_request.draft == false' in source
    assert 'uses: ./.github/workflows/quality.yml' in source
