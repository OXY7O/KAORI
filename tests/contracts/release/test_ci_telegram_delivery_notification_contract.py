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


def test_notification_workflow_is_completed_quality_run_only_and_repository_scoped() -> None:
    source = read(NOTIFY_WORKFLOW)
    quality = read(QUALITY_WORKFLOW)

    assert 'name: Delivery Notifications' in source
    assert 'name: Notify' in source
    assert 'workflow_run:' in source
    assert '- Full Admission' in source
    assert '- completed' in source
    assert 'workflow_call:' not in source
    assert 'pull_request:' not in source
    assert 'pull_request_target:' not in source
    assert 'workflow_dispatch:' not in source
    assert 'environment:' not in source
    assert source.count('runs-on: [self-hosted, linux, x64, platform-ci]') == 2
    assert 'runs-on: ubuntu-latest' not in source
    assert 'contents: read' in source
    assert 'actions: read' in source
    assert "github.repository == 'OXY7O/KAORI'" in source
    assert "github.event_name == 'workflow_run'" in source
    assert "github.event.workflow_run.name == 'Full Admission'" in source
    assert "github.event.workflow_run.event == 'push'" in source
    assert "github.event.workflow_run.status == 'completed'" in source
    assert "github.event.workflow_run.head_repository.full_name == 'OXY7O/KAORI'" in source
    assert "github.event.workflow_run.head_branch == 'kaori/staging'" in source
    assert "github.event.workflow_run.head_branch == 'main'" in source
    assert 'ref: ${{ github.event.workflow_run.head_sha }}' in source
    assert 'persist-credentials: false' in source
    assert 'TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}' in source
    assert 'TELEGRAM_CHAT_ID: ${{ vars.TELEGRAM_CHAT_ID }}' in source
    assert 'TELEGRAM_GITHUB_ACTIONS_TOPIC_ID: ${{ vars.TELEGRAM_GITHUB_ACTIONS_TOPIC_ID }}' in source
    assert 'TELEGRAM_NOTIFICATIONS_ENABLED: ${{ vars.TELEGRAM_NOTIFICATIONS_ENABLED }}' in source
    assert '--workflow-run-id "$WORKFLOW_RUN_ID"' in source
    assert '--discover-workflow-run' not in source
    assert 'KAORI_UAT_URL' not in source
    assert 'telegram-notification:' not in quality
    assert 'TELEGRAM_BOT_TOKEN' not in quality


def test_workflow_run_security_exception_is_scoped_to_trusted_push_lineage() -> None:
    source = read(NOTIFY_WORKFLOW)

    assert (
        'workflow_run: # zizmor: ignore[dangerous-triggers] trusted Full Admission push lineage is validated below'
        in source
    )
    for predicate in (
        "github.repository == 'OXY7O/KAORI'",
        "github.event.workflow_run.name == 'Full Admission'",
        "github.event.workflow_run.path == '.github/workflows/quality.yml'",
        "github.event.workflow_run.event == 'push'",
        "github.event.workflow_run.status == 'completed'",
        "github.event.workflow_run.head_repository.full_name == 'OXY7O/KAORI'",
        "github.event.workflow_run.head_branch == 'kaori/staging'",
        "github.event.workflow_run.head_branch == 'main'",
    ):
        assert predicate in source
    assert 'pull_request_target:' not in source
    assert 'pull_request:' not in source


def test_completed_run_metadata_flows_through_environment_before_shell_use() -> None:
    source = read(NOTIFY_WORKFLOW)

    assert 'WORKFLOW_EVENT: ${{ github.event.workflow_run.event }}' in source
    assert 'WORKFLOW_HEAD_BRANCH: ${{ github.event.workflow_run.head_branch }}' in source
    assert 'WORKFLOW_SOURCE_SHA: ${{ github.event.workflow_run.head_sha }}' in source
    assert 'WORKFLOW_RUN_ID: ${{ github.event.workflow_run.id }}' in source
    assert '--workflow-run-id "$WORKFLOW_RUN_ID"' in source
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


def test_completed_kaori_ci_run_requires_exact_trusted_push_identity() -> None:
    notifier = load_notifier()
    run = {
        'id': 12,
        'name': 'Full Admission',
        'path': '.github/workflows/quality.yml',
        'event': 'push',
        'head_branch': 'kaori/staging',
        'head_sha': 'abc123',
        'status': 'completed',
        'conclusion': 'success',
        'head_repository': {'full_name': 'OXY7O/KAORI'},
    }

    notifier.validate_trusted_quality_workflow_run(
        workflow_run=run,
        source_sha='abc123',
        head_branch='kaori/staging',
    )

    rejected = dict(run, head_sha='other')
    try:
        notifier.validate_trusted_quality_workflow_run(
            workflow_run=rejected,
            source_sha='abc123',
            head_branch='kaori/staging',
        )
    except RuntimeError as exc:
        assert 'source SHA' in str(exc)
    else:
        raise AssertionError('mismatched workflow-run source SHA must be rejected')


def test_notifier_has_no_trusted_push_polling_loop() -> None:
    source = read(NOTIFIER)

    assert '_WORKFLOW_WAIT_ATTEMPTS' not in source
    assert '_WORKFLOW_WAIT_SECONDS' not in source
    assert 'wait_for_quality_workflow_run' not in source
    assert 'time.sleep(' not in source
    assert '--discover-workflow-run' not in source


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
