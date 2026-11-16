"""Secrets & PKI Overview explains the actual committed-inventory prerequisite."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
OVERVIEW = ROOT / 'app/templates/secrets_pki/overview.html'


def _read() -> str:
    return OVERVIEW.read_text(encoding='utf-8')


def _state(
    *,
    provider_count: int | None,
    approved_mount_count: int | None,
    collection_state: str = 'not_collected',
    source_limit_exceeded: bool = False,
    can_manage_integrations: bool = True,
) -> list[str]:
    html = _read()
    begin = html.index('        {% if summary.source_limit_exceeded|default(false) %}')
    end = html.index('        {{ page_hero.operational_dashboard(', begin)
    stage = html[begin:end]
    result = (
        Environment()
        .from_string(
            stage
            + '\n{{ inventory_blocker_title }}|{{ inventory_blocker_label }}'
            + "|{{ inventory_blocker_info }}|{{ inventory_blocker_action_url|default('', true) }}"
            + "|{{ inventory_blocker_action_label|default('', true) }}"
        )
        .render(
            summary={
                'provider_count': provider_count,
                'approved_mount_count': approved_mount_count,
                'state': collection_state,
                'source_limit_exceeded': source_limit_exceeded,
            },
            can_manage_integrations=can_manage_integrations,
            url_for=lambda endpoint: '/vault' if endpoint == 'vault.index' else '/secrets-pki/inventory',
        )
    )
    return result.strip().split('|')


def test_saved_vault_connection_with_approved_mounts_still_requires_inventory_commit() -> None:
    stage = _state(provider_count=1, approved_mount_count=1)
    assert stage == [
        'KV v2 Inventory Not Collected',
        'Collection Required',
        'Run the KV v2 metadata inventory job.',
        '/secrets-pki/inventory',
        'Review Inventory Readiness',
    ]



def test_failed_first_inventory_collection_receives_specific_blocked_guidance() -> None:
    assert _state(
        provider_count=1, approved_mount_count=1, collection_state='failed'
    ) == [
        'KV v2 Inventory Collection Failed',
        'Collection Failed',
        'Review failed KV v2 collection.',
        '/secrets-pki/inventory',
        'Review Inventory Readiness',
    ]
    assert _state(
        provider_count=1,
        approved_mount_count=1,
        collection_state='failed',
        can_manage_integrations=False,
    )[-2:] == ['/secrets-pki/inventory', 'Review Inventory Readiness']
    assert _state(
        provider_count=1, approved_mount_count=1, collection_state='not_collected'
    )[0] == 'KV v2 Inventory Not Collected'

def test_registered_vault_without_approved_kv2_mounts_has_separate_setup_state() -> None:
    assert _state(provider_count=1, approved_mount_count=0) == [
        'KV v2 Mount Approval Required',
        'Scope Approval Required',
        'Approve KV v2 mounts for metadata inventory.',
        '/vault',
        'Review Vault Mounts',
    ]


def test_no_eligible_source_and_scope_limit_cannot_imply_healthy_zero() -> None:
    assert _state(provider_count=0, approved_mount_count=0)[:3] == [
        'Vault Source Required',
        'Setup Required',
        'Register an enabled Vault source.',
    ]
    assert _state(provider_count=None, approved_mount_count=None, source_limit_exceeded=True)[:3] == [
        'Vault Inventory Scope Review Required',
        'Scope Review Required',
        'Review Vault source and collection scope limits.',
    ]


def test_only_authorized_users_receive_provider_management_actions() -> None:
    for count, mounts in ((0, 0), (1, 0)):
        stage = _state(
            provider_count=count,
            approved_mount_count=mounts,
            can_manage_integrations=False,
        )
        assert stage[-2:] == ['', '']
    # secrets_pki.view already gates Overview and Inventory; review-only navigation remains.
    assert _state(
        provider_count=1,
        approved_mount_count=1,
        can_manage_integrations=False,
    )[-2:] == ['/secrets-pki/inventory', 'Review Inventory Readiness']


def test_mount_approval_message_is_concise_and_steps_are_operator_friendly() -> None:
    source = _read()
    mount_stage = source.split('{% elif not summary.approved_mount_count %}', 1)[1].split('{% else %}', 1)[0]
    description = 'Vault source registered. Approve a KV v2 mount to collect inventory.'
    assert len(description) <= 75
    assert f'inventory_blocker_description = "{description}"' in mount_stage
    assert '"Collect KV v2 inventory"' in mount_stage
    assert 'Run secrets_pki.inventory.sync after approval' not in mount_stage
    assert 'inventory_blocker_title = "KV v2 Mount Approval Required"' in mount_stage
    assert "inventory_blocker_action_url = url_for('vault.index') if can_manage_integrations else none" in mount_stage
    assert 'Run secrets_pki.inventory.sync and verify its committed evidence' in source


def test_blocker_copy_keeps_shared_readiness_grammar_and_is_djlint_canonical() -> None:
    source = _read()
    assert '{% set inventory_blocker_title = "KV v2 Mount Approval Required" %}' in source
    assert '{% set inventory_blocker_description = "Vault source registered.' in source
    assert "{% set inventory_blocker_title = 'KV v2 Mount Approval Required' %}" not in source
    assert "['Vault source registered', 'Approve explicit KV v2 metadata mounts'" not in source
    assert 'components/states/_blocked_state.html' in source


def test_overview_reuses_canonical_blocker_without_relaxing_inventory_gate() -> None:
    source = _read()
    Environment().parse(source)
    assert "state='normal' if summary.has_evidence else 'blocked'" in source
    assert '{% if not summary.has_evidence %}' in source
    assert 'summary.source_limit_exceeded|default(false)' in source
    assert 'inventory_blocker_title' in source
    assert 'inventory_blocker_description' in source
    assert 'inventory_blocker_steps' in source
    assert 'blocked_state_permission_granted = inventory_blocker_action_url is not none' in source
    assert 'components/states/_blocked_state.html' in source
    assert 'secrets_pki.inventory.sync' in source
    assert 'No successful committed inventory snapshot' not in source
    assert 'no successful committed inventory snapshot' in source
    assert 'summary.observed_secret_count if summary.observed_secret_count is not none' in source



def test_hero_active_scope_distinguishes_oversized_fleet_from_no_vault() -> None:
    source = _read()
    begin = source.index('        {% if summary.source_limit_exceeded|default(false) %}')
    end = source.index('        {% set action_href = ', begin)
    template = Environment().from_string(source[begin:end] + '{{ active_scope }}')

    scenarios = (
        ({'provider_count': None, 'source_limit_exceeded': True}, 'Vault Scope Review Required'),
        ({'provider_count': 0, 'source_limit_exceeded': False}, 'No Eligible Vault Source'),
        ({'provider_count': 1, 'source_limit_exceeded': False}, 'All Registered Vault Sources'),
    )
    for summary, expected in scenarios:
        assert template.render(summary=summary).strip() == expected
