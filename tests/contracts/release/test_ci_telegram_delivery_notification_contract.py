from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
QUALITY_WORKFLOW = ROOT / '.github/workflows/quality.yml'
NOTIFY_WORKFLOW = ROOT / '.github/workflows/telegram-github-actions.yml'
NOTIFIER = ROOT / 'scripts/ci_delivery_notify.py'
SPEC = ROOT / 'docs/superpowers/specs/2026-08-31-github-actions-telegram-delivery-notifications-design.md'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def load_notifier() -> ModuleType:
    assert NOTIFIER.exists(), 'GitHub Actions Telegram notification helper is not implemented yet.'
    spec = importlib.util.spec_from_file_location('kaori_ci_delivery_notify', NOTIFIER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_notification_workflow_is_trusted_branch_only_and_repository_scoped() -> None:
    source = read(NOTIFY_WORKFLOW)
    quality = read(QUALITY_WORKFLOW)

    assert 'name: KAORI Telegram Notify' in source
    assert 'name: Notify' in source
    assert 'push:' in source
    assert '- kaori/staging' in source
    assert '- main' in source
    assert 'workflow_call:' not in source
    assert 'workflow_run:' not in source
    assert 'pull_request:' not in source
    assert 'pull_request_target:' not in source
    assert 'workflow_dispatch:' not in source
    assert 'environment:' not in source
    assert source.count('runs-on: [self-hosted, linux, x64, platform-ci]') == 2
    assert 'runs-on: ubuntu-latest' not in source
    assert 'contents: read' in source
    assert 'actions: read' in source
    assert "github.repository == 'OXY7O/KAORI'" in source
    assert "github.event_name == 'push'" in source
    assert "github.ref == 'refs/heads/kaori/staging'" in source
    assert "github.ref == 'refs/heads/main'" in source
    assert 'ref: ${{ github.sha }}' in source
    assert 'persist-credentials: false' in source
    assert 'TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}' in source
    assert 'TELEGRAM_CHAT_ID: ${{ vars.TELEGRAM_CHAT_ID }}' in source
    assert 'TELEGRAM_GITHUB_ACTIONS_TOPIC_ID: ${{ vars.TELEGRAM_GITHUB_ACTIONS_TOPIC_ID }}' in source
    assert 'TELEGRAM_NOTIFICATIONS_ENABLED: ${{ vars.TELEGRAM_NOTIFICATIONS_ENABLED }}' in source
    assert '--discover-workflow-run' in source
    assert 'KAORI_UAT_URL' not in source
    assert 'telegram-notification:' not in quality
    assert 'TELEGRAM_BOT_TOKEN' not in quality


def test_push_metadata_flows_through_environment_before_shell_use() -> None:
    source = read(NOTIFY_WORKFLOW)

    assert 'WORKFLOW_EVENT: ${{ github.event_name }}' in source
    assert 'WORKFLOW_HEAD_BRANCH: ${{ github.ref_name }}' in source
    assert 'WORKFLOW_SOURCE_SHA: ${{ github.sha }}' in source
    assert '--workflow-event "$WORKFLOW_EVENT"' in source
    assert '--head-branch "$WORKFLOW_HEAD_BRANCH"' in source
    assert '--source-sha "$WORKFLOW_SOURCE_SHA"' in source
    assert '--head-branch "${{' not in source
    assert '--source-sha "${{' not in source


def test_event_routing_emits_actionable_governed_delivery_boundaries() -> None:
    notifier = load_notifier()

    expected = {
        ('staging-integration', 'success'): 'UAT_REQUIRED',
        ('post-promotion', 'success'): 'DELIVERY_COMPLETE',
        ('pr-integration', 'failure'): 'CANDIDATE_BLOCKED',
        ('staging-integration', 'failure'): 'STAGING_DELIVERY_FAILED',
        ('promotion', 'failure'): 'PROMOTION_BLOCKED',
        ('post-promotion', 'failure'): 'PRODUCTION_VERIFICATION_FAILED',
    }
    for (profile, result), event in expected.items():
        assert (
            notifier.select_event(
                profile=profile,
                execution='fast' if result == 'success' else 'full',
                admission_result=result,
                security_result='skipped',
            )
            == event
        )

    for profile in ('pr-integration', 'promotion'):
        assert (
            notifier.select_event(
                profile=profile,
                execution='full',
                admission_result='success',
                security_result='success',
            )
            is None
        )
    for profile in ('pr-integration', 'staging-integration', 'promotion', 'post-promotion'):
        assert (
            notifier.select_event(
                profile=profile,
                execution='full',
                admission_result='cancelled',
                security_result='skipped',
            )
            is None
        )


def test_profile_resolution_supports_governed_delivery_boundaries() -> None:
    notifier = load_notifier()

    assert (
        notifier.resolve_profile(
            event_name='push',
            head_branch='kaori/staging',
            base_branch='',
        )
        == 'staging-integration'
    )
    assert (
        notifier.resolve_profile(
            event_name='push',
            head_branch='main',
            base_branch='',
        )
        == 'post-promotion'
    )


def test_matching_kaori_ci_run_requires_exact_push_sha_and_branch() -> None:
    notifier = load_notifier()
    runs = [
        {
            'id': 10,
            'event': 'push',
            'head_branch': 'kaori/staging',
            'head_sha': 'other',
            'status': 'completed',
        },
        {
            'id': 11,
            'event': 'pull_request',
            'head_branch': 'kaori/staging',
            'head_sha': 'abc123',
            'status': 'completed',
        },
        {
            'id': 12,
            'event': 'push',
            'head_branch': 'kaori/staging',
            'head_sha': 'abc123',
            'status': 'completed',
            'conclusion': 'success',
            'html_url': 'https://github.com/OXY7O/KAORI/actions/runs/12',
        },
    ]

    assert (
        notifier.select_matching_workflow_run(
            runs=runs,
            source_sha='abc123',
            head_branch='kaori/staging',
        )
        == runs[2]
    )


def test_notifier_understands_concise_and_legacy_ci_job_names() -> None:
    notifier = load_notifier()

    concise = [
        {'name': 'Fast Smoke', 'conclusion': 'success'},
        {'name': 'CI Admission', 'conclusion': 'success'},
    ]
    legacy = [
        {'name': 'KAORI Fast Integration Smoke', 'conclusion': 'success'},
        {'name': 'KAORI CI Admission', 'conclusion': 'success'},
    ]
    assert notifier.infer_execution(concise) == 'fast'
    assert notifier.infer_execution(legacy) == 'fast'
    assert notifier.first_failure([{'name': 'Security', 'conclusion': 'failure'}]) == 'Security — failure'


def test_event_categories_are_stable_and_future_categories_are_reserved() -> None:
    notifier = load_notifier()

    assert notifier.event_category('CANDIDATE_BLOCKED') == 'CI / Quality'
    assert notifier.event_category('STAGING_DELIVERY_FAILED') == 'CI / Quality'
    assert notifier.event_category('UAT_REQUIRED') == 'UAT'
    assert notifier.event_category('PROMOTION_BLOCKED') == 'Promotion'
    assert notifier.event_category('DELIVERY_COMPLETE') == 'Promotion'

    spec = read(SPEC)
    assert '| CI / Quality |' in spec
    assert '| UAT |' in spec
    assert '| Promotion |' in spec
    assert '| Release |' in spec
    assert '| Deployment |' in spec

    emitted = set(notifier._EVENT_CATEGORIES)
    assert 'RELEASE_PUBLISHED' not in emitted
    assert 'DEPLOYMENT_SUCCEEDED' not in emitted


def test_uat_message_contains_operator_action_evidence_and_tracking() -> None:
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
    assert 'Stage: Staging Integration' in message
    assert 'Status: READY FOR UAT' in message
    assert 'Environment: kaori/staging' in message
    assert 'Commit: 1234567890ab' in message
    assert 'Full Admission evidence reused + Fast Integration Smoke PASS' in message
    assert 'Complete human UAT before promotion to main.' in message
    assert 'Issue: #77 · Open' in message
    assert 'PR: #79 · Merged' in message
    assert 'CI: https://github.com/OXY7O/KAORI/actions/runs/123' in message


def test_configuration_is_disabled_unless_explicitly_enabled_and_complete() -> None:
    notifier = load_notifier()

    assert notifier.configuration_status(enabled='', bot_token='', chat_id='', topic_id='') == (
        False,
        'Telegram GitHub Actions notifications are not enabled.',
    )
    assert notifier.configuration_status(enabled='true', bot_token='secret', chat_id='-100123', topic_id='') == (
        False,
        'Telegram GitHub Actions notification configuration is incomplete.',
    )
    assert notifier.configuration_status(enabled='true', bot_token='secret', chat_id='-100123', topic_id='42') == (
        True,
        'Telegram GitHub Actions notifications are configured.',
    )


def test_transport_contract_is_https_topic_aware_and_secret_safe() -> None:
    source = read(NOTIFIER)

    assert "_TELEGRAM_API: Final = 'https://api.telegram.org'" in source
    assert "'message_thread_id': topic_id" in source
    assert "'chat_id': chat_id" in source
    assert 'print(bot_token)' not in source
    assert 'print(chat_id)' not in source
    assert 'print(topic_id)' not in source
    assert 'app.integrations' not in source
    assert 'KAORI_UAT_URL' not in source
