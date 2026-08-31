from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / '.github/workflows/quality.yml'
NOTIFIER = ROOT / 'scripts/ci_delivery_notify.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def load_notifier() -> ModuleType:
    assert NOTIFIER.exists(), 'Delivery notification helper is not implemented yet.'
    spec = importlib.util.spec_from_file_location('kaori_ci_delivery_notify', NOTIFIER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workflow_uses_dedicated_environment_and_never_exposes_secrets_to_forks() -> None:
    source = read(WORKFLOW)
    assert 'name: KAORI Delivery Notification' in source
    assert 'name: kaori-delivery' in source
    assert 'TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}' in source
    assert 'TELEGRAM_DELIVERY_CHAT_ID: ${{ vars.TELEGRAM_DELIVERY_CHAT_ID }}' in source
    assert 'TELEGRAM_DELIVERY_ENABLED: ${{ vars.TELEGRAM_DELIVERY_ENABLED }}' in source
    assert 'KAORI_UAT_URL: ${{ vars.KAORI_UAT_URL }}' in source
    assert 'github.event.pull_request.head.repo.full_name == github.repository' in source
    assert 'continue-on-error: true' in source


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


def test_uat_message_contains_exact_operator_action_and_links() -> None:
    notifier = load_notifier()
    message = notifier.render_message(
        event='UAT_REQUIRED',
        profile='staging-integration',
        execution='fast',
        source_sha='1234567890abcdef',
        repository='OXY7O/KAORI',
        run_url='https://github.com/OXY7O/KAORI/actions/runs/123',
        pr_number='',
        uat_url='https://kaori.example.test/uat',
    )
    assert '🧪 KAORI · UAT Required' in message
    assert 'Environment: Staging' in message
    assert 'Commit: 1234567890ab' in message
    assert 'Full Admission evidence reused + Fast Integration Smoke PASS' in message
    assert 'Action: Complete UAT before promotion to main.' in message
    assert 'View Run: https://github.com/OXY7O/KAORI/actions/runs/123' in message
    assert 'Open KAORI UAT: https://kaori.example.test/uat' in message


def test_configuration_is_disabled_unless_explicitly_enabled_and_complete() -> None:
    notifier = load_notifier()
    assert notifier.configuration_status(enabled='', bot_token='', chat_id='') == (
        False,
        'Telegram delivery is not enabled.',
    )
    assert notifier.configuration_status(enabled='true', bot_token='', chat_id='@kaori_delivery') == (
        False,
        'Telegram delivery configuration is incomplete.',
    )
    assert notifier.configuration_status(enabled='true', bot_token='secret', chat_id='@kaori_delivery') == (
        True,
        'Telegram delivery is configured.',
    )


def test_transport_contract_is_https_only_and_does_not_log_secret_values() -> None:
    source = read(NOTIFIER)
    assert "_TELEGRAM_API = 'https://api.telegram.org'" in source
    assert "urlencode({'chat_id': chat_id, 'text': message" in source
    assert 'print(bot_token)' not in source
    assert 'print(chat_id)' not in source
    assert "response.read().decode('utf-8')" in source
