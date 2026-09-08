from pathlib import Path


def test_representative_interactions_use_canonical_authenticated_local_authority() -> None:
    interactions = Path('tests/ui/test_representative_interactions.py').read_text()
    fixtures = Path('tests/ui/conftest.py').read_text()

    assert '/auth/login' in interactions
    assert "f'{kaori_base_url}/login'" not in interactions
    assert 'pytest.skip' not in interactions
    assert 'KAORI_UI_USERNAME' not in interactions
    assert 'KAORI_UI_PASSWORD' not in interactions
    assert 'kaori_authenticated_base_url' in interactions
    assert 'def kaori_authenticated_base_url' in fixtures


def test_representative_interactions_remain_governed_browser_coverage() -> None:
    interactions = Path('tests/ui/test_representative_interactions.py').read_text()

    required_evidence = (
        'navigation',
        'theme_toggle',
        '[hx-get]',
        'dialog',
        'filter_control',
        'pagination',
        "locator('form')",
    )
    for evidence in required_evidence:
        assert evidence in interactions
