"""KAORI Identity Provider Registry actions and expanded detail UI contract (#2932)."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_registry_uses_shared_compact_accessible_view_more_action() -> None:
    registry = read('app/templates/access/identity_providers/partials/_registry.html')
    shared = read('app/templates/components/details/_expandable_row.html')

    Environment().parse(registry)
    assert "expandable.toggle_button('identity-providers'" in registry
    assert "open_label='View More', close_label='View Less', compact=true, table_action=true" in registry
    assert 'expandable.static_detail_row(detail_row_id, detail_target_id, 6)' in registry
    assert 'data-detail-toggle' in shared
    assert 'aria-expanded="false"' in shared
    assert 'aria-controls="{{ row_id }}"' in shared
    assert "url_for('identity_providers.edit', provider_id=provider.id)" not in registry
    assert 'access/identity_providers/partials/_provider_detail.html' in registry
    assert 'registry_ui.footer(' in registry
    assert "form_id='identity-provider-registry-filter-form'" in registry


def test_expanded_detail_reuses_unified_resource_sheet_instead_of_four_cards() -> None:
    detail = read('app/templates/access/identity_providers/partials/_provider_detail.html')
    macros = read('app/templates/components/details/_detail_content.html')

    Environment().parse(detail)
    assert '{% import "components/details/_detail_content.html" as detail_ui %}' in detail
    assert 'detail_ui.resource_sheet()' in detail
    assert detail.count('detail_ui.inventory_section(') == 2
    assert detail.count('compact_layout=true') == 2
    assert 'data-kaori-idp-expanded-detail' in detail
    assert 'data-kaori-idp-connection-facts' in detail
    assert 'data-kaori-idp-access-facts' in detail
    assert 'xl:grid-cols-4' not in detail
    assert 'detail_ui.detail_card(' not in detail
    assert 'data-kaori-unified-resource-sheet' in macros
    assert 'data-kaori-inventory-section-layout' in macros
    assert detail.index("'Provider & Connection'") < detail.index("'Identity & Access'")
    assert 'row.connection' in detail
    assert 'row.credential_reference' in detail
    assert 'row.access_model.label' in detail
    assert 'provider.default_role' in detail
    assert 'row.identity_links' in detail
    # The main table already owns configuration and enabled indicators.
    assert 'row.configuration.label' not in detail
    assert 'row.state.label' not in detail


def test_actions_match_activity_audit_table_buttons_and_preserve_permission_gates() -> None:
    detail = read('app/templates/access/identity_providers/partials/_provider_detail.html')
    shared = read('app/templates/components/table_primitives.html')
    activity = read('app/templates/access/activity_audit/partials/_administrative_evidence.html')
    disclosure = read('app/templates/components/details/_expandable_row.html')

    Environment().parse(detail)
    Environment().parse(disclosure)
    assert '{% import "components/table.html" as table_ui %}' in detail
    assert detail.count('table_ui.action_classes()') == 3
    assert 'action_button.classes(' not in detail
    assert 'table_ui.action_classes()' in activity
    assert 'table_primitives.action_classes()' in disclosure
    assert 'table_action=false' in disclosure
    assert 'table_action=true' in read('app/templates/access/identity_providers/partials/_registry.html')
    assert 'data-kaori-idp-detail-actions' in detail
    assert "url_for('identity_providers.validate', provider_id=provider.id)" in detail
    assert 'name="csrf_token"' in detail
    assert "url_for('identity_providers.edit', provider_id=provider.id)" in detail
    assert "url_for('identity_providers.directory_provisioning')" in detail
    assert "current_user.has_permission('identity_providers.manage')" in detail
    assert "current_user.has_permission('identity_providers.provision')" in detail
    assert "'directory'" in detail
    assert 'Read-only provider details' in detail
    assert 'inline-flex min-h-9' not in detail
    assert 'bg-kaori-primary px-3' not in detail
    assert 'min-h-8 px-2.5' in shared
    assert 'border-outline-default bg-surface-card text-content-secondary' in shared
    assert detail.count('class="h-3.5 w-3.5"') == 3


def test_provider_detail_keeps_copy_compact_and_removes_repeated_field_rules() -> None:
    """Keep only section boundaries; leave individual facts clean and legible."""
    detail = read('app/templates/access/identity_providers/partials/_provider_detail.html')
    shared = read('app/templates/components/details/_detail_content.html')

    Environment().parse(detail)
    assert "description='Adapter identity and connection.'" in detail
    assert "description='Identity projection and KAORI access.'" in detail
    assert 'Registered adapter identity and credential reference' not in detail
    assert 'The external directory owns credentials; KAORI governs account projection' not in detail

    # The global shared inventory row keeps its dividers for other consumers.
    # Identity Provider is a compact density override limited to its two fact grids.
    assert detail.count('[&>div]:border-0 [&>div]:py-1.5') == 2
    assert detail.count('gap-y-1 sm:grid-cols-2') == 2
    assert 'border-b border-outline-subtle py-2.5' in shared
    assert 'detail_ui.inventory_section(' in detail
    assert 'data-kaori-idp-detail-actions' in detail
