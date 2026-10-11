from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[4]
TEMPLATES = ROOT / 'app/templates/storage/object_storage/inventory'


def test_system_and_bucket_tables_explain_source_bounded_fields() -> None:
    expected = {
        'systems': ('Release', 'Inventory Assets', 'Snapshot', 'Status'),
        'buckets': ('Type', 'Quota', 'Protection', 'Last Snapshot'),
    }
    ids = []
    for category, headers in expected.items():
        source = (TEMPLATES / category / 'partials/_table_content.html').read_text(encoding='utf-8')
        assert '{% import "components/info_tip.html" as info_tip %}' in source
        assert source.count('info_tip.render(') == len(headers)
        assert '<thead' in source and '<tbody' in source
        for header in headers:
            assert f'>{header} {{{{ info_tip.render(' in source
        ids += re.findall(r"info_tip.render\('(storage-inventory-[^']+)'", source)

    assert len(ids) == 8 and len(set(ids)) == len(ids)


def test_storage_help_does_not_claim_missing_quota_or_policy_is_healthy() -> None:
    bucket = (TEMPLATES / 'buckets/partials/_table_content.html').read_text(encoding='utf-8')
    assert 'Missing quota evidence does not imply unlimited capacity.' in bucket
    assert 'displayed evidence is not an audit verdict.' in bucket
    assert 'current live provider request' in bucket


def test_shared_info_tip_remains_keyboard_and_touch_accessible() -> None:
    shared = (ROOT / 'app/templates/components/info_tip.html').read_text(encoding='utf-8')
    js = (ROOT / 'app/static/js/info_tips.js').read_text(encoding='utf-8')
    assert 'aria-label="More information about {{ title }}"' in shared
    assert 'aria-expanded="false"' in shared
    assert 'role="tooltip"' in shared
    assert "'focusin'" in js and "'pointerover'" in js and "'click'" in js
