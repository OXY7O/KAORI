from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
QUALITY_WORKFLOW = ROOT / '.github/workflows/quality.yml'
NOTIFY_WORKFLOW = ROOT / '.github/workflows/telegram-github-actions.yml'
NOTIFIER = ROOT / 'scripts/ci_delivery_notify.py'
SPEC = (
    ROOT
    / 'docs/superpowers/specs/2026-08-31-github-actions-telegram-delivery-notifications-design.md'
)


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def load_notifier() -> ModuleType:
    assert NOTIFIER.exists(), (
        'GitHub Actions Telegram notification helper is not implemented yet.'
    )
    spec = importlib.util.spec_from_file_location('kaori_ci_delivery_notify', NOTIFIER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_notification_workflow_is_separate_environment_scoped_and_trusted() -> None:
    source = read(NOTIFY_WORKFLOW)
    quality = read(QUALITY_WORKFLOW)
    assert 'name: KAORI GitHub Actions Telegram Notification' in source
    assert 'workflow_run:' in source
    assert 'workflows: ["KAORI CI"]' in source
    assert 'types: [completed]' in source
    assert 'name: kaori-github-actions' in source
    assert 'runs-on: ubuntu-latest' in source
    assert 'actions: read' in source
    assert 'pull-requests: read' in source
    assert 'TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}' in source
    assert 'TELEGRAM_CHAT_ID: ${{ vars.TELEGRAM_CHAT_ID }}' in source
    assert (
        'TELEGRAM_GITHUB_ACTIONS_TOPIC_ID: '
        '${{ vars.TELEGRAM_GITHUB_ACTIONS_TOPIC_ID }}' in source
    )
    assert (
        'TELEGRAM_NOTIFICATIONS_ENABLED: '
        '${{ vars.TELEGRAM_NOTIFICATIONS_ENABLED }}' in source
    )
    assert (
        'github.event.workflow_run.head_repository.full_name == github.repository'
        in source
    )
    assert 'continue-on-error: true' in source
    assert 'workflow_run.pull_requests[0]' not in source
    assert 'KAORI_UAT_URL' not in source
    assert 'KAORI GitHub Actions Telegram Notification' not in quality


def test_workflow_event_metadata_is_not_interpolated_directly_into_shell() -> None:
    source = read(NOTIFY_WORKFLOW)
    assert 'WORKFLOW_HEAD_BRANCH: ${{ github.event.workflow_run.head_branch }}' in source
    assert 'WORKFLOW_RUN_URL: ${{ github.event.workflow_run.html_url }}' in source
    assert '--head-branch "$WORKFLOW_HEAD_BRANCH"' in source
    assert '--run-url "$WORKFLOW_RUN_URL"' in source
    assert '--head-branch "${{ github.event.workflow_run.head_branch }}"' not in source
    assert '--run-url "${{ github.event.workflow_run.html_url }}"' not in source


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
    assert (
        notifier.select_event(
            profile='pr-integration',
            execution='full',
            admission_result='skipped',
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


def test_pull_request_context_prefers_exact_open_candidate_and_fails_ambiguous() -> None:
    notifier = load_notifier()
    source_sha = 'abc123'
    pulls = [
        {
            'number': 62,
            'state': 'closed',
            'head': {'ref': 'feature', 'sha': source_sha},
            'base': {'ref': 'kaori/staging'},
        },
        {
            'number': 64,
            'state': 'open',
            'head': {'ref': 'feature', 'sha': source_sha},
            'base': {'ref': 'kaori/staging'},
        },
    ]
    assert notifier.select_pull_request_context(
        pull_requests=pulls,
        head_branch='feature',
        source_sha=source_sha,
    ) == ('kaori/staging', '64')

    ambiguous = [
        {
            'number': 64,
            'state': 'open',
            'head': {'ref': 'feature', 'sha': source_sha},
            'base': {'ref': 'kaori/staging'},
        },
        {
            'number': 65,
            'state': 'open',
            'head': {'ref': 'feature', 'sha': source_sha},
            'base': {'ref': 'main'},
        },
    ]
    assert notifier.select_pull_request_context(
        pull_requests=ambiguous,
        head_branch='feature',
        source_sha=source_sha,
    ) == ('', '')


def test_event_categories_are_stable_and_operator_facing() -> None:
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


def test_uat_message_contains_category_exact_operator_action_and_github_link() -> None:
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
    ) == (
        False,
        'Telegram GitHub Actions notifications are not enabled.',
    )
    assert notifier.configuration_status(
        enabled='true',
        bot_token='secret',
        chat_id='-100123',
        topic_id='',
    ) == (
        False,
        'Telegram GitHub Actions notification configuration is incomplete.',
    )
    assert notifier.configuration_status(
        enabled='true',
        bot_token='secret',
        chat_id='-100123',
        topic_id='42',
    ) == (
        True,
        'Telegram GitHub Actions notifications are configured.',
    )


def test_transport_contract_is_https_topic_aware_and_does_not_log_secret_values() -> None:
    source = read(NOTIFIER)
    assert "_TELEGRAM_API: Final = 'https://api.telegram.org'" in source
    assert "'message_thread_id': topic_id" in source
    assert "'chat_id': chat_id" in source
    assert 'print(bot_token)' not in source
    assert 'print(chat_id)' not in source
    assert 'print(topic_id)' not in source
    assert "response.read().decode('utf-8')" in source
    assert 'app.integrations' not in source
    assert 'KAORI_UAT_URL' not in source


def test_reserved_release_and_deployment_categories_do_not_emit_until_future_workflows_exist() -> None:
    notifier = load_notifier()
    emitted = set(notifier._EVENT_CATEGORIES)
    assert 'Release' not in emitted
    assert 'Deployment' not in emitted
    assert 'RELEASE_PUBLISHED' not in emitted
    assert 'DEPLOYMENT_SUCCEEDED' not in emitted
