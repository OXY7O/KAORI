import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_domain_search_has_explicit_label_relationship() -> None:
    page = (ROOT / 'app/templates/platform_operations/data_lifecycle/index.html').read_text(encoding='utf-8')
    assert 'for="data-lifecycle-domain-search"' in page
    assert re.search(r'id="data-lifecycle-domain-search"\s+type="search"', page)


def test_archive_history_filter_labels_are_programmatically_associated() -> None:
    history = (ROOT / 'app/templates/platform_operations/data_lifecycle/partials/_history.html').read_text(
        encoding='utf-8'
    )
    for name in (
        'archive_domain',
        'archive_status',
        'archive_trigger',
        'archive_mode',
        'archive_storage',
        'archive_search',
    ):
        control_id = 'data-lifecycle-' + name.replace('_', '-')
        assert f'for="{control_id}"' in history
        assert re.search(rf'id="{control_id}"\s+name="{name}"', history)
