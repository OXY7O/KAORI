from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY_WORKFLOW = ROOT / '.github/workflows/quality.yml'
TRUSTED_NOTIFIER_SHA = '43ca843a09835a53bd72a7513a82f891164736d6'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_quality_calls_trusted_telegram_notifier_after_admission() -> None:
    source = read(QUALITY_WORKFLOW)
    trusted_call = f'uses: OXY7O/KAORI/.github/workflows/telegram-github-actions.yml@{TRUSTED_NOTIFIER_SHA}'

    assert 'telegram-notification:' in source
    assert 'name: GitHub Actions Telegram Delivery' in source
    assert 'needs: admission' in source
    assert 'if: ${{ always() }}' in source
    assert trusted_call in source
    assert 'TELEGRAM_BOT_TOKEN' not in source
    assert 'TELEGRAM_CHAT_ID' not in source
    assert 'TELEGRAM_GITHUB_ACTIONS_TOPIC_ID' not in source
    assert 'TELEGRAM_NOTIFICATIONS_ENABLED' not in source


def test_quality_does_not_reintroduce_privileged_notification_trigger() -> None:
    source = read(QUALITY_WORKFLOW)

    assert 'workflow_run:' not in source
    assert 'pull_request_target:' not in source
