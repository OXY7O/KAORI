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


def test_notification_workflow_is_reusable_environment_scoped_and_trusted() -> None:
    source = read(NOTIFY_WORKFLOW)
    quality = read(QUALITY_WORKFLOW)

    assert 'name: KAORI GitHub Actions Telegram Notification' in source
    assert 'workflow_call:' in source
    assert 'workflow_run:' not in source
    assert 'pull_request_target:' not in source
    assert 'name: kaori-github-actions' in source
    assert 'runs-on: ubuntu-latest' in source
    assert 'contents: read' in source
    assert 'actions: read' in source
    assert 'pull-requests: read' not in source
    assert "github.repository == 'OXY7O/KAORI'" in source
    assert 'github.event.pull_request.draft == false' in source
    assert 'github.event.pull_request.head.repo.full_name == github.repository' in source
    assert 'ref: ${{ github.event.repository.default_branch }}' in source
    assert 'persist-credentials: false' in source
    assert 'id: trusted_checkout' in source
    assert source.count('continue-on-error: true') == 2
    assert "steps.trusted_checkout.outcome != 'success'" in source
    assert "steps.trusted_checkout.outcome == 'success'" in source
    assert 'TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}' in source
    assert 'TELEGRAM_CHAT_ID: ${{ vars.TELEGRAM_CHAT_ID }}' in source
    assert 'TELEGRAM_GITHUB_ACTIONS_TOPIC_ID: ${{ vars.TELEGRAM_GITHUB_ACTIONS_TOPIC_ID }}' in source
    assert 'TELEGRAM_NOTIFICATIONS_ENABLED: ${{ vars.TELEGRAM_NOTIFICATIONS_ENABLED }}' in source
    assert 'KAORI_UAT_URL' not in source
    assert 'KAORI GitHub Actions Telegram Notification' not in quality


def test_caller_metadata_flows_through_environment_before_shell_use() -> None:
    source = read(NOTIFY_WORKFLOW)

    assert 'WORKFLOW_RUN_ID: ${{ github.run_id }}' in source
    assert 'WORKFLOW_EVENT: ${{ github.event_name }}' in source
    assert 'WORKFLOW_HEAD_BRANCH: ${{ github.head_ref || github.ref_name }}' in source
    assert 'WORKFLOW_BASE_BRANCH: ${{ github.base_ref }}' in source
    assert 'WORKFLOW_SOURCE_SHA: ${{ github.event.pull_request.head.sha || github.sha }}' in source
    assert 'WORKFLOW_PR_NUMBER: ${{ github.event.pull_request.number }}' in source
    assert '--workflow-run-id "$WORKFLOW_RUN_ID"' in source
    assert '--workflow-event "$WORKFLOW_EVENT"' in source
    assert '--head-branch "$WORKFLOW_HEAD_BRANCH"' in source
    assert '--base-branch "$WORKFLOW_BASE_BRANCH"' in source
    assert '--source-sha "$WORKFLOW_SOURCE_SHA"' in source
    assert '--pr-number "$WORKFLOW_PR_NUMBER"' in source
    assert '--head-branch "${{' not in source
    assert '--source-sha "${{' not in source


def test_event_routing_is_actionable_and_profile_aware() -> None:
    notifier = load_notifier()

    assert (
        notifier.select_event(
            profile='pr-integration',
            execution='full',
            admission_result='success',
            security_result='success',
        )
        == 'FULL_ADMISSION_PASSED'
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
            profile='promotion',
            execution='fast',
            admission_result='success',
            security_result='skipped',
        )
        == 'PROMOTION_VALIDATED'
    )
    assert (
        notifier.select_event(
            profile='post-promotion',
            execution='fast',
            admission_result='success',
            security_result='skipped',
        )
        == 'PROMOTION_SUCCEEDED'
    )
    assert (
        notifier.select_event(
            profile='pr-integration',
            execution='full',
            admission_result='failure',
            security_result='failure',
        )
        == 'SECURITY_GATE_FAILED'
    )
    assert (
        notifier.select_event(
            profile='staging-integration',
            execution='fast',
            admission_result='failure',
            security_result='skipped',
        )
        == 'DELIVERY_FAILED'
    )
    assert (
        notifier.select_event(
            profile='pr-integration',
            execution='fast',
            admission_result='success',
            security_result='skipped',
        )
        is None
    )


def test_profile_resolution_supports_governed_delivery_boundaries() -> None:
    notifier = load_notifier()

    assert (
        notifier.resolve_profile(
            event_name='pull_request',
            head_branch='feature',
            base_branch='kaori/staging',
        )
        == 'pr-integration'
    )
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
            event_name='pull_request',
            head_branch='kaori/staging',
            base_branch='main',
        )
        == 'promotion'
    )
    assert (
        notifier.resolve_profile(
            event_name='push',
            head_branch='main',
            base_branch='',
        )
        == 'post-promotion'
    )


def test_event_categories_are_stable_and_future_categories_are_reserved() -> None:
    notifier = load_notifier()

    assert notifier.event_category('FULL_ADMISSION_PASSED') == 'CI / Quality'
    assert notifier.event_category('DELIVERY_FAILED') == 'CI / Quality'
    assert notifier.event_category('SECURITY_GATE_FAILED') == 'Security'
    assert notifier.event_category('UAT_REQUIRED') == 'UAT'
    assert notifier.event_category('PROMOTION_VALIDATED') == 'Promotion'
    assert notifier.event_category('PROMOTION_SUCCEEDED') == 'Promotion'

    spec = read(SPEC)
    assert '| CI / Quality |' in spec
    assert '| Security |' in spec
    assert '| UAT |' in spec
    assert '| Promotion |' in spec
    assert '| Release |' in spec
    assert '| Deployment |' in spec

    emitted = set(notifier._EVENT_CATEGORIES)
    assert 'RELEASE_PUBLISHED' not in emitted
    assert 'DEPLOYMENT_SUCCEEDED' not in emitted


def test_uat_message_contains_exact_operator_action_and_github_link() -> None:
    notifier = load_notifier()
    message = notifier.render_message(
        event='UAT_REQUIRED',
        profile='staging-integration',
        execution='fast',
        source_sha='1234567890abcdef',
        repository='OXY7O/KAORI',
        run_url='https://github.com/OXY7O/KAORI/actions/runs/123',
        pr_number='',
    )

    assert '🧪 KAORI · UAT Required' in message
    assert 'Category: UAT' in message
    assert 'Environment: Staging' in message
    assert 'Commit: 1234567890ab' in message
    assert 'Full Admission evidence reused + Fast Integration Smoke PASS' in message
    assert 'Action: Complete UAT before promotion to main.' in message
    assert 'View Run: https://github.com/OXY7O/KAORI/actions/runs/123' in message
    assert 'Open KAORI UAT' not in message


def test_configuration_is_disabled_unless_explicitly_enabled_and_complete() -> None:
    notifier = load_notifier()

    assert notifier.configuration_status(
        enabled='',
        bot_token='',
        chat_id='',
        topic_id='',
    ) == (False, 'Telegram GitHub Actions notifications are not enabled.')
    assert notifier.configuration_status(
        enabled='true',
        bot_token='secret',
        chat_id='-100123',
        topic_id='',
    ) == (False, 'Telegram GitHub Actions notification configuration is incomplete.')
    assert notifier.configuration_status(
        enabled='true',
        bot_token='secret',
        chat_id='-100123',
        topic_id='42',
    ) == (True, 'Telegram GitHub Actions notifications are configured.')


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
