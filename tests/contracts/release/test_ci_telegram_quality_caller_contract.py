from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
QUALITY_WORKFLOW = ROOT / '.github/workflows/quality.yml'
NOTIFY_WORKFLOW = ROOT / '.github/workflows/telegram-github-actions.yml'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_quality_does_not_call_or_receive_telegram_delivery_configuration() -> None:
    source = read(QUALITY_WORKFLOW)

    assert 'telegram-notification:' not in source
    assert 'GitHub Actions Telegram Delivery' not in source
    assert 'telegram-github-actions.yml' not in source
    assert 'TELEGRAM_BOT_TOKEN' not in source
    assert 'TELEGRAM_CHAT_ID' not in source
    assert 'TELEGRAM_GITHUB_ACTIONS_TOPIC_ID' not in source
    assert 'TELEGRAM_NOTIFICATIONS_ENABLED' not in source


def test_telegram_workflow_run_trigger_is_not_a_privileged_pr_path() -> None:
    source = read(NOTIFY_WORKFLOW)

    assert 'pull_request:' not in source
    assert 'pull_request_target:' not in source
    assert 'workflow_call:' not in source
    assert 'workflow_run:' in source
    assert "github.event.workflow_run.event == 'push'" in source
    assert "github.event.workflow_run.head_repository.full_name == 'OXY7O/KAORI'" in source
    assert "github.event.workflow_run.head_branch == 'kaori/staging'" in source
    assert "github.event.workflow_run.head_branch == 'main'" in source
