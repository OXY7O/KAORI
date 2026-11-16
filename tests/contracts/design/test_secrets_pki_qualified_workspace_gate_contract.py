"""Inventory and Lifecycle stay navigable but suppress unqualified operational sections."""

from pathlib import Path

from jinja2 import Environment

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
    for kv2, pki, expected in [
        (False, 'not_collected', True),
        (False, 'ready', False),
        (True, 'not_collected', False),
        (True, 'ready', False),
    ]:
        assert (
            _gate(
                source,
                "lifecycle_unqualified = not summary.has_evidence and pki_validity.status != 'ready'",
                summary={'has_evidence': kv2},
                pki_validity={'status': pki},
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
            summary={'provider_count': providers, 'approved_mount_count': mounts}
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
    inventory_route = routes.split('def inventory()', 1)[1].split(
        '@secrets_pki_bp.get', 1
    )[0]

    assert "can_execute_inventory=current_user.has_permission('secrets_pki.sync')" in inventory_route
    assert "and current_user.has_permission('jobs.execute')" in inventory_route
    assert "and current_user.has_permission('jobs.view')" in inventory_route
    assert "@permission_required('jobs.view')\ndef configuration(" in job_routes
    assert "{% if can_execute_inventory %}" in source
    assert "url_for('jobs.configuration', job_key='secrets_pki.inventory.sync')" in source
    assert 'inventory_blocker_href is not none' in source
