from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TELEGRAM_WORKFLOW = ROOT / '.github' / 'workflows' / 'telegram-github-actions.yml'


def test_platform_ci_telegram_jobs_use_python3() -> None:
    source = TELEGRAM_WORKFLOW.read_text(encoding='utf-8')

    assert source.count('python3 scripts/ci_delivery_notify.py') == 2
    assert 'python scripts/ci_delivery_notify.py' not in source
