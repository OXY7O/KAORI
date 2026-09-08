from pathlib import Path


REPRESENTATIVE_INTERACTIONS = Path('tests/ui/test_representative_interactions.py')
UI_CONFTEXT = Path('tests/ui/conftest.py')


def test_representative_browser_auth_uses_canonical_local_authority() -> None:
    source = REPRESENTATIVE_INTERACTIONS.read_text(encoding='utf-8')

    assert '/auth/login' in source
    assert "KAORI_UI_USERNAME" not in source
    assert "KAORI_UI_PASSWORD" not in source
    assert "pytest.skip" not in source
    assert 'kaori_authenticated_base_url' in source


def test_authenticated_browser_fixture_is_deterministic_and_local() -> None:
    source = UI_CONFTEXT.read_text(encoding='utf-8')

    assert 'def kaori_authenticated_base_url' in source
    assert "create_app('testing')" in source
    assert 'db.create_all()' in source
    assert 'User(' in source
