from pathlib import Path

TEMPLATE = Path('app/templates/users/external_identities.html')


def _source() -> str:
    return TEMPLATE.read_text(encoding='utf-8')


def test_ldap_page_uses_shared_kaori_flow_component() -> None:
    source = _source()
    assert 'components/info_flow.html' in source
    assert "'How LDAP Provisioning Works'" in source
    assert "'Before Searching'" in source
    assert 'provisioning_flow_steps' in source
    assert 'before_searching_steps' in source


def test_flow_order_is_explicit_and_operational() -> None:
    source = _source()
    expected = [
        'Prepare the Provider',
        'Find One Identity',
        'Assign KAORI Access',
        'Provision and Authenticate',
        'Validate the Provider',
        'Confirm Runtime Secrets',
        'Prepare the Role',
        'Check Identity Uniqueness',
    ]
    positions = [source.index(item) for item in expected]
    assert positions == sorted(positions)


def test_authentication_boundary_uses_kaori_violet_contract() -> None:
    source = _source()
    assert 'Authentication Boundary' in source
    assert 'border-brand-outline bg-kaori-soft/70' in source
    assert 'Credential Owner' in source
    assert 'LDAP Directory' in source
    assert 'Identity Link and Authorization' in source


def test_static_headings_are_title_case() -> None:
    source = _source()
    forbidden = [
        'Directory boundary',
        'Provider configuration controls discovery',
        'Directory identity search',
        'Directory search results',
        'How LDAP provisioning works',
        'Authentication boundary',
        'Before searching',
        'No enabled LDAP provider',
        'No matching directory identity',
        'Search the directory to begin',
    ]
    for text in forbidden:
        assert text not in source
