from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[5]
TEMPLATES = ROOT / 'app/templates/storage/object_storage/inventory'


def test_system_and_bucket_guides_appear_once_beside_table_titles() -> None:
    descriptions = {
        'systems': ('Provider Release', 'Inventory Assets', 'System Inventory Snapshot', 'System Inventory Status'),
        'buckets': ('Object Storage Type', 'Bucket Quota', 'Bucket Protection', 'Last Committed Snapshot'),
    }
    ids = []
    for resource, terms in descriptions.items():
        table = (TEMPLATES / resource / 'partials/_table_content.html').read_text(encoding='utf-8')
        title = (TEMPLATES / resource / 'partials/_table_card.html').read_text(encoding='utf-8')
        assert 'info_tip.render(' not in table
        assert 'components/info_tip.html' not in table
        assert '<thead' in table and '<tbody' in table
        assert 'components/info_tip.html' in title
        assert title.count('info_tip.render(') == 1
        assert 'title_extra=info_tip.render(' in title
        assert 'items=[' in title
        for term in terms:
            assert term in title
        ids.extend(re.findall(r"info_tip.render\('(storage-inventory-[^']+)'", title))

    assert len(ids) == 2 and len(set(ids)) == len(ids)


def test_storage_title_help_preserves_missing_evidence_interpretation() -> None:
    title = (TEMPLATES / 'buckets/partials/_table_card.html').read_text(encoding='utf-8')
    assert 'Missing quota evidence does not imply unlimited capacity.' in title
    assert 'displayed evidence is not an audit verdict.' in title
    assert 'current live provider request' in title


def test_shared_info_tip_remains_keyboard_and_touch_accessible() -> None:
    shared = (ROOT / 'app/templates/components/info_tip.html').read_text(encoding='utf-8')
    js = (ROOT / 'app/static/js/info_tips.js').read_text(encoding='utf-8')
    assert 'aria-label="More information about {{ title }}"' in shared
    assert 'aria-expanded="false"' in shared
    assert 'role="tooltip"' in shared
    assert "'focusin'" in js and "'pointerover'" in js and "'click'" in js
