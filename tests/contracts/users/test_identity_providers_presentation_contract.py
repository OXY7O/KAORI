from pathlib import Path

TEMPLATE = Path('app/templates/users/providers/index.html')


def _source() -> str:
    return TEMPLATE.read_text(encoding='utf-8')


def test_identity_provider_hero_uses_kaori_context_metrics() -> None:
    source = _source()
    assert 'Provider Portfolio' in source
    assert 'Authentication Sources' in source
    assert '>Configured<' in source
    assert '>Enabled<' in source
    assert 'Add Provider' in source
    assert 'Provision LDAP' in source
    assert 'Add a provider, validate its live integration' not in source


def test_credential_boundary_uses_kaori_violet_boundary_pattern() -> None:
    source = _source()
    assert 'Secret Ownership' in source
    assert 'Credential Boundary' in source
    assert 'KAORI Stores' in source
    assert 'Runtime Owns' in source
    assert 'border-brand-outline bg-kaori-soft/70' in source
    assert 'Credential boundary' not in source
    assert 'border-status-info-border bg-status-info-soft' not in source


def test_identity_provider_section_titles_use_title_case() -> None:
    source = _source()
    assert 'Configured Providers' in source
    assert 'Access Model' in source
    assert 'Activation Sequence' in source
