"""Authentication Security UAT visual refinement follows approved KAORI patterns (#3166)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/access/authentication_security/partials/_page_content.html'


def _template() -> str:
    return TEMPLATE.read_text(encoding='utf-8')


def _overview() -> str:
    source = _template()
    return source.split("{% if active_tab == 'overview' %}", 1)[1].split("{% elif active_tab == 'mfa' %}", 1)[0]


def test_template_parses_and_reuses_existing_kaori_shared_components() -> None:
    source = _template()
    Environment().parse(source)
    assert 'components/page_hero.html' in source
    assert 'components/table_label.html' in source
    assert 'components/workspace_tabs.html' in source
    assert 'workspace_tabs.render_navigation(' in source
    assert 'authentication-security-page' in source


def test_hero_metrics_have_compact_one_line_copy() -> None:
    source = _template()
    assert "'TOTP & recovery follow policy.'" in source
    assert "'Turnstile verifies sign-ins.'" in source
    assert 'TOTP and recovery challenge are governed by the selected policy' not in source
    assert 'Cloudflare Siteverify checked for login when enabled' not in source
    assert 'Governed Changes' in source
    assert 'Read Only' in source


def test_overview_has_three_grounded_posture_tiles_and_operational_hierarchy() -> None:
    overview = _overview()
    assert 'Authentication Assurance Posture' in overview
    assert 'Security Control Summaries' not in overview
    assert 'authentication-control-summary-heading' not in overview
    assert 'aria-label="Authentication security controls"' in overview
    assert 'class="grid gap-4 xl:grid-cols-3"' in overview
    assert 'Operational Boundaries' in overview
    assert 'Governed Here' in overview
    assert 'Managed Elsewhere' in overview
    assert 'components/workspace_tabs' not in overview
    assert "mfa_policy_mode != 'disabled'" in overview
    assert "bot_mode == 'always'" in overview
    assert "'required_privileged': 'Required · Privileged'" in overview
    assert "'required_all': 'Required · All Users'" in overview
    assert 'bot_has_secret and bot_site_key and bot_hostname' in overview
    assert 'Single active login generation' in overview
    assert 'Configured adapters do not establish external provider availability or individual enrollment.' in overview


def test_overview_reuses_existing_access_tab_routes_and_never_mutates_policy() -> None:
    overview = _overview()
    for tab in ('mfa', 'bot', 'sessions'):
        assert f"url_for('access.authentication_security.index', tab='{tab}')" in overview
    assert '<form' not in overview
    assert 'hx-post=' not in overview
    assert 'secret_key' not in overview
    assert 'csrf_token()' not in overview


def test_kaori_canonical_posture_guide_replaces_inline_header_help() -> None:
    source = _template()
    overview = _overview()
    assert '{% import "components/info_tip.html" as info_tip %}' in source
    assert "'authentication-assurance-posture-guide'" in overview
    assert "'Authentication assurance posture'" in overview
    assert "variant='guide'" in overview
    assert "placement='right'" in overview
    shared = (ROOT / 'app/templates/access/authentication_security/partials/_assurance_summary.html').read_text(
        encoding='utf-8'
    )
    assert "'authentication-posture'," in overview
    assert 'aria-labelledby="{{ id }}-heading"' in shared
    assert 'id="{{ id }}-heading"' in shared
    assert 'Current KAORI policy and session enforcement at a glance.' not in overview
    assert 'Review enforcement boundaries and open the appropriate policy workspace.' not in overview
    assert 'rounded-xl border border-outline-default bg-surface-card' in overview


def test_operational_boundary_content_is_balanced_and_separate_from_auth_logic() -> None:
    overview = _overview()
    area = overview.split('aria-labelledby="authentication-boundaries-heading"', 1)[1]
    assert 'Governed Here' in area
    assert 'Managed Elsewhere' in area
    assert 'Controls governed in Access' in area
    assert 'Related capability ownership' in area
    assert area.count('<li class="flex items-start gap-3">') == 6
    for label in (
        'MFA assurance',
        'Turnstile provider setup and sign-in enforcement.',
        'Session Security',
        'Account &amp; Authentication',
        'Identity Providers',
        'Separate security workstreams',
    ):
        assert label in area
    assert '<form' not in area
    assert 'hx-post=' not in area


def test_other_security_configuration_tabs_still_present() -> None:
    source = _template()
    assert "{% elif active_tab == 'mfa' %}" in source
    assert "{% elif active_tab == 'bot' %}" in source
    assert "url_for('access.authentication_security.save_mfa_policy')" in source
    assert "url_for('access.authentication_security.save_bot_policy')" in source
    assert 'Session Security' in source
