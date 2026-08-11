from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_settings_final_lock_is_release_gated_and_documented() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    readme = read('app/settings/README.md')
    lock = read('docs/design/KAORI_SETTINGS_LOCK_V1.md')

    assert 'python scripts/verify_settings_final_lock.py' in quality_gate
    assert 'Settings v1 is final-locked' in readme
    assert 'Status: **FINAL LOCKED**' in lock
    assert 'General Settings' in lock
    assert 'Account & Authentication' in lock


def test_settings_final_lock_retires_obsolete_side_context_partials() -> None:
    for relative in (
        'app/templates/settings/general/partials/_impact_information.html',
        'app/templates/settings/account/partials/_profile_information.html',
        'app/templates/settings/account/partials/_activity_information.html',
    ):
        assert not (ROOT / relative).exists()


def test_settings_active_surfaces_avoid_page_local_style_drift() -> None:
    for path in sorted((ROOT / 'app/templates/settings').rglob('*.html')):
        source = path.read_text(encoding='utf-8')
        assert 'text-[10px]' not in source
        assert 'tracking-[' not in source
        assert 'font-extrabold' not in source
        assert ' border-red-' not in source
        assert ' bg-red-' not in source
        assert ' text-red-' not in source
