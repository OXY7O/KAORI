from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_catalog_initial_active_state_matches_click_and_selection() -> None:
    content = (ROOT / 'app/templates/platform_operations/jobs/configuration/_workspace.html').read_text(
        encoding='utf-8'
    )
    # Selected and clicked identities use equivalent normalization; Jinja
    # may retain formatter whitespace between the two replace filters.
    assert "activeJob: '{{ (selected_job_key or '')|replace('.', '-') |replace('/', '-') }}'" in content
    assert '@click="activeJob = \'' in content
    assert '\'; ensureActiveVisible()"' in content
    assert "activeJob === '{{ item.key|replace('.', '-') |replace('/', '-') }}'" in content
