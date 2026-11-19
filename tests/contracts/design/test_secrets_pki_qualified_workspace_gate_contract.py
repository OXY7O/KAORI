"""Inventory and Lifecycle stay navigable but suppress unqualified operational sections."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
INVENTORY = ROOT / 'app/templates/secrets_pki/inventory.html'
LIFECYCLE = ROOT / 'app/templates/secrets_pki/lifecycle.html'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _gate(source: str, expression: str, **context: object) -> bool:
    start = source.index('{% set ' + expression.split(' = ')[0] + ' = ')
    end = source.index('%}', start) + 2
    rendered = (
        Environment().from_string(source[start:end] + '\n{{ ' + expression.split(' = ')[0] + ' }}').render(**context)
    )
    return rendered.strip() == 'True'


def test_inventory_is_blocked_for_saved_but_unqualified_vault() -> None:
    source = _read(INVENTORY)
    Environment().parse(source)
    assert _gate(source, 'inventory_unqualified = not summary.has_evidence', summary={'has_evidence': False})
    assert not _gate(source, 'inventory_unqualified = not summary.has_evidence', summary={'has_evidence': True})
    assert source.count('{% if inventory_unqualified %}') == 2
    assert 'summary.approved_mount_count' in source
    assert 'KV v2 Mount Approval Required' in source
    assert 'KV v2 Inventory Not Collected' in source
    assert 'Vault Source Required' in source
    assert 'components/states/_blocked_state.html' in source
    assert 'inventory_blocker_href is not none' in source
    assert 'can_execute_inventory and summary.approved_mount_count' in source
    assert 'secrets_pki.inventory.sync' in source


def test_inventory_does_not_show_operational_zero_tiles_without_qualification() -> None:
    source = _read(INVENTORY)
    blocked_branch = source.split('{% if inventory_unqualified %}', 2)[2].split('{% else %}', 1)[0]
    assert 'components/states/_blocked_state.html' in blocked_branch
    assert "metric_card.render('Enabled Vault Sources'" not in blocked_branch
    assert "metric_card.render('Approved KV v2 Mounts'" not in blocked_branch
    assert 'Committed Inventory Coverage' in source
    assert 'summary.observed_secret_count if summary.observed_secret_count is not none' in source


def test_lifecycle_requires_qualified_kv2_or_independent_pki_evidence() -> None:
    source = _read(LIFECYCLE)
    Environment().parse(source)
    for kv2_status, pki_status, expected in [
        ('not_configured', 'not_collected', True),
        ('incomplete_evidence', 'not_collected', True),
        ('blocked', 'not_collected', True),
        ('ready', 'not_collected', False),
        ('observed_empty', 'not_collected', False),
        ('incomplete_evidence', 'ready', False),
        ('not_configured', 'ready', False),
        ('ready', 'ready', False),
    ]:
        assert (
            _gate(
                source,
                "lifecycle_unqualified = not lifecycle_kv2_qualified and pki_validity.status != 'ready'",
                lifecycle_kv2_qualified=kv2_status in {'ready', 'observed_empty'},
                pki_validity={'status': pki_status},
            )
            is expected
        )
    assert source.count('{% if lifecycle_unqualified %}') == 2
    assert 'KV v2 Mount Approval Required' in source
    assert 'Lifecycle Evidence Not Collected' in source
    assert 'components/states/_blocked_state.html' in source


def test_lifecycle_qualified_independent_pki_and_routes_remain_intact() -> None:
    source = _read(LIFECYCLE)
    routes = _read(ROOT / 'app/secrets_pki/routes.py')
    assert "pki_validity.status == 'ready'" in source
    assert 'Version Lifecycle' in source
    assert 'Certificate Validity' in source
    assert 'Kubernetes TLS Consumer Correlation' in source
    assert "@permission_required('secrets_pki.view')\ndef inventory(" in routes
    assert "@permission_required('secrets_pki.view')\ndef lifecycle(" in routes


def test_lifecycle_hero_info_is_one_natural_desktop_line_with_full_blocker_below() -> None:
    source = _read(LIFECYCLE)
    begin = source.index('{% set lifecycle_blocker_info = ')
    end = source.index('%}', begin) + 2
    template = Environment().from_string(source[begin:end] + '{{ lifecycle_blocker_info }}')
    cases = (
        (0, 0, 'Register Vault to qualify lifecycle evidence.'),
        (1, 0, 'Approve KV v2 mounts or qualify independent PKI evidence.'),
        (1, 1, 'Collect qualified KV v2 or PKI evidence.'),
    )
    for providers, mounts, expected in cases:
        result = template.render(
            summary={'provider_count': providers, 'approved_mount_count': mounts},
            lifecycle_version_incomplete=False,
        )
        assert result.strip() == expected
        assert len(result.strip()) < 65

    assert 'lifecycle_blocker_info,' in source
    assert 'blocked_state_description = lifecycle_blocker_description' in source
    assert 'whitespace-nowrap' not in source


def test_inventory_job_links_require_view_permission_of_destination() -> None:
    source = _read(INVENTORY)
    routes = _read(ROOT / 'app/secrets_pki/routes.py')
    job_routes = _read(ROOT / 'app/platform_operations/jobs/routes.py')
    inventory_route = routes.split('def inventory()', 1)[1].split('@secrets_pki_bp.get', 1)[0]

    assert "can_execute_inventory=current_user.has_permission('secrets_pki.sync')" in inventory_route
    assert "and current_user.has_permission('jobs.execute')" in inventory_route
    assert "and current_user.has_permission('jobs.view')" in inventory_route
    assert "@permission_required('jobs.view')\ndef configuration(" in job_routes
    assert '{% if can_execute_inventory %}' in source
    assert "url_for('jobs.configuration', job_key='secrets_pki.inventory.sync')" in source
    assert 'inventory_blocker_href is not none' in source


def test_over_limit_vault_inventory_uses_scope_review_not_inventory_execution() -> None:
    source = _read(INVENTORY)
    begin = source.index('{% set inventory_unqualified = ')
    end = source.index('<section', begin)
    template = Environment().from_string(
        source[begin:end]
        + '{{ inventory_blocker_title }}|{{ inventory_blocker_action|default("", true) }}'
        + '|{{ inventory_blocker_href|default("", true) }}'
    )
    scope = {
        'has_evidence': False,
        'source_limit_exceeded': True,
        'provider_count': 1,
        'approved_mount_count': 100,
    }

    def render(manage: bool) -> str:
        return template.render(
            summary=scope,
            can_manage_integrations=manage,
            can_execute_inventory=True,
            url_for=lambda endpoint, **kwargs: '/vault' if endpoint == 'vault.index' else '/jobs',
        ).strip()

    assert render(True) == 'Vault Inventory Scope Review Required|Review Vault Scope|/vault'
    assert render(False) == 'Vault Inventory Scope Review Required||'
    assert 'Reduce collection scope to approved limits' in source
    assert 'not summary.source_limit_exceeded|default(false)' in source


def test_over_limit_lifecycle_keeps_independent_pki_qualification() -> None:
    source = _read(LIFECYCLE)
    begin = source.index('{% set lifecycle_kv2_qualified = ')
    end = source.index('{{ lifecycle_navigation.render', begin)
    template = Environment().from_string(
        source[begin:end] + '{{ lifecycle_blocker_title }}|{{ lifecycle_blocker_info }}'
    )
    result = template.render(
        summary={
            'has_evidence': False,
            'source_limit_exceeded': True,
            'provider_count': 1,
            'approved_mount_count': 100,
        },
        kv2_version_posture={'status': 'incomplete_evidence'},
        pki_validity={'status': 'not_collected'},
        can_manage_integrations=False,
        url_for=lambda endpoint: '/vault',
    ).strip()
    assert result == ('Vault Inventory Scope Review Required|Review Vault scope or qualify independent PKI evidence.')
    assert "lifecycle_unqualified = not lifecycle_kv2_qualified and pki_validity.status != 'ready'" in source


def test_inventory_hero_scope_does_not_confuse_overflow_with_missing_vault() -> None:
    source = _read(INVENTORY)
    begin = source.index('{% set inventory_unqualified = ')
    end = source.index('<section', begin)
    template = Environment().from_string(source[begin:end] + '{{ inventory_scope_label }}|{{ inventory_scope_helper }}')
    scenarios = (
        (
            {'provider_count': None, 'approved_mount_count': None, 'source_limit_exceeded': True},
            'Scope Review Required|Review approved scope',
        ),
        (
            {'provider_count': 0, 'approved_mount_count': 0, 'source_limit_exceeded': False},
            'No Vault Source|Registration required',
        ),
        (
            {'provider_count': 1, 'approved_mount_count': 0, 'source_limit_exceeded': False},
            'Registered Vault Sources|Mount approval required',
        ),
    )
    for summary, expected in scenarios:
        result = template.render(
            summary=summary,
            can_manage_integrations=False,
            can_execute_inventory=False,
            url_for=lambda endpoint, **kwargs: '/vault',
        )
        assert result.strip() == expected

    assert "('server', 'Active Scope', inventory_scope_label, inventory_scope_helper)" in source


def test_failed_first_collection_has_distinct_inventory_blocker_and_short_hero_info() -> None:
    source = _read(INVENTORY)
    start = source.index('{% set inventory_unqualified = ')
    end = source.index('<section', start)
    stage = Environment().from_string(
        source[start:end]
        + '{{ inventory_blocker_title }}|{{ inventory_blocker_info }}|'
        + '{{ inventory_blocker_steps[-1] }}|{{ inventory_blocker_action|default("", true) }}'
    )
    summary = {
        'has_evidence': False,
        'state': 'failed',
        'provider_count': 1,
        'approved_mount_count': 1,
        'source_limit_exceeded': False,
    }
    context = {
        'summary': summary,
        'can_manage_integrations': False,
        'can_execute_inventory': True,
        'url_for': lambda endpoint, **kwargs: '/inventory-job',
    }
    assert stage.render(**context).strip() == (
        'KV v2 Inventory Collection Failed|Review the failed KV v2 inventory job.|'
        'Review failed inventory collection|Open Inventory Job'
    )
    summary['state'] = 'not_collected'
    assert stage.render(**context).strip().startswith('KV v2 Inventory Not Collected|Collect approved KV v2 inventory.')
    assert 'blocked_state_description = inventory_blocker_description' in source
    assert 'blocked_state_label = "Collection Failed" if inventory_collection_failed' in source


def test_lifecycle_failed_first_collection_keeps_independent_pki_path() -> None:
    source = _read(LIFECYCLE)
    start = source.index('{% set lifecycle_kv2_qualified = ')
    end = source.index('{{ lifecycle_navigation.render', start)
    stage = Environment().from_string(
        source[start:end]
        + '{{ lifecycle_unqualified }}|{{ lifecycle_blocker_title }}|'
        + '{{ lifecycle_blocker_info }}'
    )
    summary = {
        'has_evidence': False,
        'state': 'failed',
        'provider_count': 1,
        'approved_mount_count': 1,
        'source_limit_exceeded': False,
    }

    def render(pki_status: str) -> str:
        return stage.render(
            summary=summary,
            kv2_version_posture={'status': 'incomplete_evidence'},
            pki_validity={'status': pki_status},
            can_manage_integrations=False,
            url_for=lambda endpoint: '/vault',
        ).strip()

    assert render('not_collected') == (
        'True|Lifecycle Collection Failed|Review failed collection or qualify independent PKI.'
    )
    assert render('ready').startswith('False|Lifecycle Collection Failed|')
    assert 'blocked_state_label = "Collection Failed" if summary.state == ' in source


def test_stale_or_partial_historical_kv2_does_not_open_lifecycle_without_qualified_pki() -> None:
    source = _read(LIFECYCLE)
    begin = source.index('{% set lifecycle_kv2_qualified = ')
    end = source.index('{{ lifecycle_navigation.render', begin)
    stage = Environment().from_string(
        source[begin:end]
        + '{{ lifecycle_unqualified }}|{{ lifecycle_blocker_title }}|'
        + '{{ lifecycle_blocker_info }}|{{ lifecycle_version_incomplete }}'
    )
    for kv2_status in ('incomplete_evidence', 'blocked', 'not_configured'):
        result = stage.render(
            summary={
                'has_evidence': True,
                'state': 'stale',
                'provider_count': 1,
                'approved_mount_count': 1,
                'source_limit_exceeded': False,
            },
            kv2_version_posture={'status': kv2_status},
            pki_validity={'status': 'not_collected'},
            can_manage_integrations=False,
            url_for=lambda endpoint: '/vault',
        ).strip()
        assert result == ('True|KV v2 Evidence Not Qualified|Refresh KV v2 evidence or qualify independent PKI.|True')

    # Current-generation qualified empty inventory is a real, valid zero.
    qualified = stage.render(
        summary={
            'has_evidence': True,
            'state': 'committed',
            'provider_count': 1,
            'approved_mount_count': 1,
            'source_limit_exceeded': False,
        },
        kv2_version_posture={'status': 'observed_empty'},
        pki_validity={'status': 'not_collected'},
        can_manage_integrations=False,
        url_for=lambda endpoint: '/vault',
    ).strip()
    assert qualified.startswith('False|')
    assert 'blocked_state_description = lifecycle_blocker_description' in source
    assert 'components/states/_blocked_state.html' in source


def test_lifecycle_blocker_routes_qualified_mounts_to_inventory_for_read_only_viewers() -> None:
    source = _read(LIFECYCLE)
    begin = source.index('{% set lifecycle_kv2_qualified = ')
    end = source.index('{{ lifecycle_navigation.render', begin)
    stage = Environment().from_string(
        source[begin:end] + '{{ lifecycle_blocker_url|default("", true) }}|{{ lifecycle_inventory_review }}'
    )
    data = {
        'has_evidence': True,
        'state': 'stale',
        'provider_count': 1,
        'approved_mount_count': 1,
        'source_limit_exceeded': False,
    }

    def render(mounts: int, manage: bool) -> str:
        data['approved_mount_count'] = mounts
        return stage.render(
            summary=data,
            kv2_version_posture={'status': 'incomplete_evidence'},
            pki_validity={'status': 'not_collected'},
            can_manage_integrations=manage,
            url_for=lambda endpoint: '/inventory' if endpoint == 'secrets_pki.inventory' else '/vault',
        ).strip()

    assert render(1, False) == '/inventory|True'
    assert render(0, False) == '|0'
    assert render(0, True) == '/vault|0'
    assert 'blocked_state_action_label = "Review Inventory Readiness" if lifecycle_inventory_review' in source
    assert 'blocked_state_permission_granted = lifecycle_blocker_url is not none' in source


def test_secrets_pki_workspaces_compile_entire_jinja_templates() -> None:
    """Catch syntax failures on full page compilation before browser UAT."""
    env = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')), autoescape=True)
    for name in (
        'secrets_pki/overview.html',
        'secrets_pki/inventory.html',
        'secrets_pki/lifecycle.html',
    ):
        assert env.get_template(name).name == name


def test_lifecycle_blocker_steps_render_for_each_readiness_stage() -> None:
    source = _read(LIFECYCLE)
    start = source.index(
        '        {% if summary.source_limit_exceeded|default(false) %}',
        source.index('{% set lifecycle_blocker_info = '),
    )
    end = source.index('{% set lifecycle_inventory_review = ', start)
    template = Environment().from_string(source[start:end] + "{{ lifecycle_blocker_steps|join(' | ') }}")
    scenarios = (
        (True, 1, 201, 'blocked', False, 'Qualify committed KV v2 or PKI evidence'),
        (False, 0, 0, 'blocked', False, 'Collect qualified evidence'),
        (False, 1, 0, 'blocked', False, 'Collect qualified lifecycle evidence'),
        (False, 1, 1, 'failed', False, 'Review failed collection before retry'),
        (False, 1, 1, 'stale', True, 'Verify qualified lifecycle evidence'),
        (False, 1, 1, 'not_collected', False, 'Collect and verify lifecycle evidence'),
    )
    for over_limit, sources, mounts, state, incomplete, expected in scenarios:
        rendered = template.render(
            summary={
                'source_limit_exceeded': over_limit,
                'provider_count': sources,
                'approved_mount_count': mounts,
                'state': state,
            },
            lifecycle_version_incomplete=incomplete,
        )
        steps = rendered.strip().split(' | ')
        assert len(steps) == 3
        assert steps[-1] == expected
