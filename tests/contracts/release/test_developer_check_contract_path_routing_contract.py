from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / '.github' / 'workflows' / 'developer-check.yml'


def test_developer_check_routes_each_contract_family_to_focused_tests() -> None:
    source = WORKFLOW.read_text(encoding='utf-8')

    families = (
        'access',
        'analytics',
        'architecture',
        'dashboards',
        'definitions',
        'design',
        'integrations',
        'intelligence',
        'kubernetes',
        'platform_operations',
        'release',
        'reports',
        'settings',
        'storage',
        'welcome',
    )

    for family in families:
        pattern = f'tests/contracts/{family}/*)'
        selection = f'selected_tests[tests/contracts/{family}]=1'
        assert pattern in source, family
        assert selection in source, family


def test_developer_check_preserves_release_fallback_for_unfocused_contract_changes() -> None:
    source = WORKFLOW.read_text(encoding='utf-8')

    assert "paths='tests/contracts/release'" in source
