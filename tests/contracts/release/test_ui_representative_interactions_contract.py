from pathlib import Path


INTERACTIONS = Path('tests/ui/test_representative_interactions.py')
CONFTEST = Path('tests/ui/conftest.py')


def test_representative_interactions_use_canonical_auth_login_route() -> None:
    source = INTERACTIONS.read_text(encoding='utf-8')

    assert '/auth/login' in source
    assert "f'{kaori_base_url}/login'" not in source


def test_representative_interactions_cannot_silently_skip_governed_evidence() -> None:
    source = INTERACTIONS.read_text(encoding='utf-8')

    assert 'pytest.skip' not in source
    assert 'kaori_authenticated_base_url' in source


def test_ui_harness_provides_deterministic_authenticated_local_authority() -> None:
    source = CONFTEST.read_text(encoding='utf-8')

    assert 'def kaori_authenticated_base_url' in source
    assert "create_app('testing')" in source
