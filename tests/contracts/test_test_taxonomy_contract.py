from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_auth_domain_gate_contains_only_functional_test_modules() -> None:
    names = {path.name for path in (ROOT / 'tests/auth').glob('test_*.py')}

    assert not any('architecture' in name for name in names)
    assert not any('migration' in name for name in names)
    assert not any('debug' in name for name in names)


def test_non_functional_test_categories_have_separate_roots() -> None:
    assert (ROOT / 'tests/contracts').is_dir()
    assert (ROOT / 'tests/migrations').is_dir()
    assert (ROOT / 'tests/debug').is_dir()


def test_ldap_warning_filter_is_narrow_and_does_not_hide_all_deprecations() -> None:
    config = (ROOT / 'pytest.ini').read_text()

    assert 'ldap3\\.utils\\.asn1' in config
    assert 'tagMap is deprecated' in config
    assert 'typeMap is deprecated' in config
    assert 'ignore::DeprecationWarning' not in config
