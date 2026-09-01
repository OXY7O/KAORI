from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
QUALITY_WORKFLOW = ROOT / '.github/workflows/quality.yml'
NOTIFY_WORKFLOW = ROOT / '.github/workflows/telegram-github-actions.yml'
NOTIFIER = ROOT / 'scripts/ci_delivery_notify.py'
CONTEXT = ROOT / 'scripts/ci_delivery_context.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_notifier() -> ModuleType:
    return load_module(NOTIFIER, 'kaori_ci_delivery_notify_context')


def load_context() -> ModuleType:
    return load_module(CONTEXT, 'kaori_ci_delivery_context_contract')


def test_trusted_notifier_observes_pr_failures_without_privileged_pr_trigger() -> None:
    source = read(NOTIFY_WORKFLOW)
    quality = read(QUALITY_WORKFLOW)

    assert 'schedule:' in source
    assert '*/5 * * * *' in source
    assert 'pull-requests: read' in source
    assert 'issues: read' in source
    assert '--scan-pr-failures' in source
    assert 'workflow_run:' not in source
    assert 'pull_request_target:' not in source
    assert 'pull_request:' not in source
    assert 'TELEGRAM_BOT_TOKEN' not in quality


def test_actionable_delivery_boundaries_have_stage_specific_events() -> None:
    notifier = load_notifier()

    assert (
        notifier.select_event(
            profile='pr-integration',
            execution='full',
            admission_result='failure',
            security_result='failure',
        )
        == 'CANDIDATE_BLOCKED'
    )
    assert (
        notifier.select_event(
            profile='promotion',
            execution='fast',
            admission_result='failure',
            security_result='skipped',
        )
        == 'PROMOTION_BLOCKED'
    )
    assert (
        notifier.select_event(
            profile='staging-integration',
            execution='fast',
            admission_result='failure',
            security_result='skipped',
        )
        == 'STAGING_DELIVERY_FAILED'
    )
    assert (
        notifier.select_event(
            profile='post-promotion',
            execution='fast',
            admission_result='failure',
            security_result='skipped',
        )
        == 'PRODUCTION_VERIFICATION_FAILED'
    )
    assert (
        notifier.select_event(
            profile='staging-integration',
            execution='fast',
            admission_result='success',
            security_result='skipped',
        )
        == 'UAT_REQUIRED'
    )
    assert (
        notifier.select_event(
            profile='post-promotion',
            execution='fast',
            admission_result='success',
            security_result='skipped',
        )
        == 'DELIVERY_COMPLETE'
    )


def test_friendly_uat_message_explains_work_testability_and_tracking() -> None:
    notifier = load_notifier()
    context = notifier.DeliveryContext(
        issue_number='77',
        issue_title='Improve GitHub Actions Telegram delivery context and failure coverage',
        issue_status='Open',
        issue_url='https://github.com/OXY7O/KAORI/issues/77',
        pr_number='79',
        pr_title='feat(ci): improve Telegram delivery context #77',
        pr_status='Merged',
        pr_url='https://github.com/OXY7O/KAORI/pull/79',
    )

    message = notifier.render_message(
        event='UAT_REQUIRED',
        profile='staging-integration',
        execution='fast',
        source_sha='1234567890abcdef',
        repository='OXY7O/KAORI',
        run_url='https://github.com/OXY7O/KAORI/actions/runs/123',
        context=context,
    )

    assert '🧪 KAORI · Ready for UAT' in message
    assert '📌 Work' in message
    assert '#77 Improve GitHub Actions Telegram delivery context and failure coverage' in message
    assert '📍 Delivery' in message
    assert 'Stage: Staging Integration' in message
    assert 'Status: READY FOR UAT' in message
    assert 'Environment: kaori/staging' in message
    assert '🧪 Testing' in message
    assert 'Ready for UAT' in message
    assert 'Validate: Improve GitHub Actions Telegram delivery context and failure coverage' in message
    assert '✅ Evidence' in message
    assert 'Full Admission evidence reused + Fast Integration Smoke PASS' in message
    assert 'Commit: 1234567890ab' in message
    assert '➡️ Next' in message
    assert 'Complete human UAT' in message
    assert '🔗 Tracking' in message
    assert 'Issue: #77 · Open' in message
    assert 'https://github.com/OXY7O/KAORI/issues/77' in message
    assert 'PR: #79 · Merged' in message
    assert 'https://github.com/OXY7O/KAORI/pull/79' in message
    assert 'CI: https://github.com/OXY7O/KAORI/actions/runs/123' in message


def test_blocked_candidate_message_says_not_to_test_and_names_failed_gate() -> None:
    notifier = load_notifier()
    context = notifier.DeliveryContext(
        issue_number='77',
        issue_title='Improve GitHub Actions Telegram delivery context and failure coverage',
        issue_status='Open',
        issue_url='https://github.com/OXY7O/KAORI/issues/77',
        pr_number='79',
        pr_title='feat(ci): improve Telegram delivery context #77',
        pr_status='Ready',
        pr_url='https://github.com/OXY7O/KAORI/pull/79',
    )

    message = notifier.render_message(
        event='CANDIDATE_BLOCKED',
        profile='pr-integration',
        execution='full',
        source_sha='abcdef1234567890',
        repository='OXY7O/KAORI',
        run_url='https://github.com/OXY7O/KAORI/actions/runs/456',
        context=context,
        failure_detail='Security — failure',
    )

    assert '❌ KAORI · Candidate Blocked' in message
    assert 'Status: BLOCKED' in message
    assert 'Do not test yet' in message
    assert 'Failure: Security — failure' in message
    assert 'Return the work to Draft repair' in message


def test_missing_delivery_metadata_degrades_without_fabricated_issue_or_pr() -> None:
    notifier = load_notifier()
    message = notifier.render_message(
        event='UAT_REQUIRED',
        profile='staging-integration',
        execution='fast',
        source_sha='1234567890abcdef',
        repository='OXY7O/KAORI',
        run_url='https://github.com/OXY7O/KAORI/actions/runs/123',
        context=notifier.DeliveryContext(),
    )

    assert 'Delivery context unavailable' in message
    assert 'Issue: #' not in message
    assert 'PR: #' not in message


def test_issue_and_pr_context_helpers_follow_governed_linkage() -> None:
    context_module = load_context()

    assert context_module.linked_issue_number('Refs #77') == 77
    assert context_module.linked_issue_number('Closes #35') == 35
    assert context_module.linked_issue_number('No governed issue link here') is None

    pull_requests = [
        {'number': 90, 'base': {'ref': 'main'}, 'head': {'ref': 'kaori/staging'}},
        {'number': 79, 'base': {'ref': 'kaori/staging'}, 'head': {'ref': 'feat-77'}},
    ]
    assert context_module.select_delivery_pr(pull_requests, profile='staging-integration')['number'] == 79
    assert context_module.select_delivery_pr(pull_requests, profile='post-promotion')['number'] == 90


def test_scheduled_failure_observer_selects_only_unnotified_actionable_pr_run() -> None:
    notifier = load_notifier()
    runs = [
        {
            'id': 103,
            'event': 'pull_request',
            'status': 'completed',
            'conclusion': 'success',
            'pull_requests': [{'number': 81, 'base': {'ref': 'kaori/staging'}, 'head': {'ref': 'feat-ok'}}],
        },
        {
            'id': 102,
            'event': 'pull_request',
            'status': 'completed',
            'conclusion': 'failure',
            'pull_requests': [{'number': 80, 'base': {'ref': 'main'}, 'head': {'ref': 'kaori/staging'}}],
        },
        {
            'id': 101,
            'event': 'pull_request',
            'status': 'completed',
            'conclusion': 'failure',
            'pull_requests': [{'number': 79, 'base': {'ref': 'kaori/staging'}, 'head': {'ref': 'feat-77'}}],
        },
    ]
    artifacts = [{'name': 'kaori-telegram-quality-run-102'}]

    selected = notifier.select_unnotified_pr_failure(runs=runs, artifacts=artifacts)

    assert selected is not None
    assert selected['id'] == 101
    assert notifier.pr_run_profile(selected) == 'pr-integration'
