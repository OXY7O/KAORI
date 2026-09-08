from pathlib import Path


REPRESENTATIVE_INTERACTIONS = Path('tests/ui/test_representative_interactions.py')


def _source() -> str:
    return REPRESENTATIVE_INTERACTIONS.read_text(encoding='utf-8')


def test_representative_interactions_use_canonical_auth_login_route() -> None:
    source = _source()
    assert "f'{kaori_base_url}/auth/login'" in source
    assert "f'{kaori_base_url}/login'" not in source


def test_representative_interactions_do_not_silently_skip_missing_credentials() -> None:
    source = _source()
    credentials_block = source.split('def _credentials()', 1)[1].split('\n\ndef _login', 1)[0]
    assert 'pytest.skip' not in credentials_block
    assert 'KAORI_UI_USERNAME' in credentials_block
    assert 'KAORI_UI_PASSWORD' in credentials_block
