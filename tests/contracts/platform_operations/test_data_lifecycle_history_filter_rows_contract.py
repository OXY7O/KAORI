"""Archive History filter, page-size and empty-state source contracts (#2974)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
HISTORY = ROOT / 'app/templates/platform_operations/data_lifecycle/partials/_history.html'


def test_filter_change_preserves_page_size_and_resets_page_to_first() -> None:
    source = HISTORY.read_text(encoding='utf-8')
    Environment().parse(source)
    form = source.split('    <form method="get"', 1)[1].split('    </form>', 1)[0]
    assert 'hx-get="{{ url_for(\'platform_operations.data_lifecycle.index\') }}"' in form
    assert 'hx-target="#data-lifecycle-history"' in form
    assert 'hx-push-url="true"' in form
    assert '<input type="hidden" name="tab" value="history">' in form
    assert '<input type="hidden" name="archive_per_page" value="{{ pager.per_page }}">' in form
    assert 'name="archive_page"' not in form
    for key in (
        'archive_domain',
        'archive_status',
        'archive_trigger',
        'archive_mode',
        'archive_storage',
        'archive_search',
    ):
        assert f'name="{key}"' in form

    # Other controls already preserve the chosen per-page value.
    assert 'archive_page=1, archive_per_page=pager.per_page' in source
    assert 'name="archive_per_page"' in source
    assert 'value="{{ size }}"' in source


def test_no_history_empty_state_does_not_claim_preview_creates_archive_evidence() -> None:
    source = HISTORY.read_text(encoding='utf-8')
    assert 'empty_state_title = "No Archive History Found"' in source
    assert ('empty_state_description = "Archive executions appear here. Preview does not create archives."') in source
    assert 'Run a preview or archive operation' not in source
