import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_catalog_initial_active_state_matches_click_and_selection() -> None:
    content = (ROOT / 'app/templates/platform_operations/jobs/configuration/_workspace.html').read_text(
        encoding='utf-8'
    )
    # Jinja whitespace around filters is cosmetic; identical keys are not.
    normalized = re.sub(r'\\s+\\|replace', '|replace', content)
    assert "activeJob: '{{ (selected_job_key or '')|replace('.', '-')|replace('/', '-') }}'" in normalized
    assert "@click=\"activeJob = '{{ item.key|replace('.', '-') |replace('/', '-') }}'\"" in normalized
    assert "activeJob === '{{ item.key|replace('.', '-') |replace('/', '-') }}'" in normalized
