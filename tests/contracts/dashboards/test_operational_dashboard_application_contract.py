import re
from pathlib import Path

from app.common.operational_tabs import normalize_operational_tab as shared_normalize_operational_tab
from app.common.pagination import DEFAULT_PER_PAGE, PER_PAGE_OPTIONS
from app.dashboards.common.operational import (
    DASHBOARD_PAGE_SIZES,
    DEFAULT_DASHBOARD_PAGE_SIZE,
    DEFAULT_OPERATIONAL_DASHBOARD_TAB,
    OPERATIONAL_DASHBOARD_TABS,
    is_htmx_request,
    normalize_dashboard_page_size,
    normalize_operational_tab,
)


def test_operational_dashboard_tabs_are_one_ordered_contract() -> None:
    assert OPERATIONAL_DASHBOARD_TABS == ('overview', 'capacity', 'signals', 'reporting')
    assert DEFAULT_OPERATIONAL_DASHBOARD_TAB == 'overview'
    assert normalize_operational_tab(None) == 'overview'
    assert normalize_operational_tab(' CAPACITY ') == 'capacity'
    assert normalize_operational_tab('unknown') == 'overview'


def test_operational_dashboard_tab_normalization_is_shared_without_reverse_dependency() -> None:
    root = Path(__file__).resolve().parents[3]
    source = (root / 'app/secrets_pki/routes.py').read_text(encoding='utf-8')
    assert 'from app.common.operational_tabs import normalize_operational_tab' in source
    assert 'from app.dashboards.common.operational import normalize_operational_tab' not in source
    assert normalize_operational_tab is shared_normalize_operational_tab
    assert shared_normalize_operational_tab(' SIGNALS ') == 'signals'
    assert shared_normalize_operational_tab('invalid') == 'overview'


def test_locked_dashboard_verifier_checks_shared_tab_owner_and_explicit_facade() -> None:
    root = Path(__file__).resolve().parents[3]
    shared = (root / 'app/common/operational_tabs.py').read_text(encoding='utf-8')
    dashboard = (root / 'app/dashboards/common/operational.py').read_text(encoding='utf-8')
    verifier = (root / 'scripts/verify_operational_dashboard_standard.py').read_text(encoding='utf-8')
    standard = (root / 'docs/design/patterns/OPERATIONAL_DASHBOARD.md').read_text(encoding='utf-8')
    assert 'OPERATIONAL_DASHBOARD_TABS: tuple[str, ...] = (' in shared
    assert 'OPERATIONAL_DASHBOARD_TABS: tuple[str, ...] = (' not in dashboard
    for symbol in (
        'OPERATIONAL_DASHBOARD_TABS',
        'DEFAULT_OPERATIONAL_DASHBOARD_TAB',
        'normalize_operational_tab',
    ):
        assert f'{symbol} as {symbol}' in dashboard
    assert "COMMON_OPERATIONAL_TABS = ROOT / 'app' / 'common' / 'operational_tabs.py'" in verifier
    assert 'common_operational_tabs = _read(COMMON_OPERATIONAL_TABS)' in verifier
    assert 'app/common/operational_tabs.py' in standard


def test_workspace_tab_presentation_matches_application_contract() -> None:
    root = Path(__file__).resolve().parents[3]
    workspace = (root / 'app/templates/components/operational_dashboard_workspace.html').read_text(encoding='utf-8')
    rendered_keys = tuple(re.findall(r"\('([^']+)', '[^']+', '[^']+'\)", workspace))
    assert rendered_keys == OPERATIONAL_DASHBOARD_TABS


def test_dashboard_page_sizes_delegate_to_canonical_pagination_contract() -> None:
    assert DASHBOARD_PAGE_SIZES is PER_PAGE_OPTIONS
    assert DEFAULT_DASHBOARD_PAGE_SIZE == DEFAULT_PER_PAGE == 5
    for value in (5, '10', 25, '50'):
        assert normalize_dashboard_page_size(value) == int(value)
    for value in (None, 0, -1, '5000', 'invalid'):
        assert normalize_dashboard_page_size(value) == 5


def test_htmx_detection_is_explicit_and_case_insensitive() -> None:
    assert is_htmx_request({'HX-Request': 'true'}) is True
    assert is_htmx_request({'HX-Request': 'TRUE'}) is True
    assert is_htmx_request({'HX-Request': ' false '}) is False
    assert is_htmx_request({}) is False
