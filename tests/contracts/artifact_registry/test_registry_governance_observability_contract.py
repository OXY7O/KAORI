import re
from io import StringIO
from pathlib import Path
from tokenize import COMMENT, generate_tokens

ROOT = Path(__file__).resolve().parents[3]


def test_registry_governance_is_committed_and_provider_neutral() -> None:
    models = (ROOT / 'app/models/registry.py').read_text()
    governance = (ROOT / 'app/artifact_registry/governance.py').read_text()
    harbor = (ROOT / 'app/integrations/registry/providers/harbor/governance.py').read_text()

    assert 'class RegistryGovernanceState' in models
    assert 'class RegistryProjectGovernance' in models
    assert 'class RegistryReplicationPolicy' in models
    assert 'HarborInstance' not in governance
    assert 'RegistryGovernanceCollector' in governance
    assert 'collect_harbor_governance' in harbor
    assert 'retention_status' in harbor
    assert 'immutability_status' in harbor
    assert 'ReplicationPolicyRecord' in harbor


def test_registry_metrics_reuses_canonical_metrics_source_binding() -> None:
    taxonomy = (ROOT / 'app/definitions/catalogs/integrations/taxonomy.yaml').read_text()
    metrics_contract = (
        ROOT / 'app/definitions/catalogs/integrations/observability/metrics_source/contract.yaml'
    ).read_text()
    validators = (ROOT / 'app/integrations/observability/metrics_source/binding_validators/__init__.py').read_text()
    registry_validator = (
        ROOT / 'app/integrations/observability/metrics_source/binding_validators/registry_asset.py'
    ).read_text()

    assert 'asset_type: registry_instance' in taxonomy
    assert 'asset_type: registry_instance' in metrics_contract
    assert 'profile_key: registry-metrics-v1' in metrics_contract
    assert "register_binding_validator(PROMETHEUS_HTTP_ADAPTER, 'registry_instance'" in validators
    assert 'IntegrationBinding' in registry_validator
    assert 'RegistryHarborMetricsAuditor' in registry_validator


def test_artifact_registry_has_no_direct_prometheus_transport() -> None:
    for path in (ROOT / 'app/artifact_registry').glob('*.py'):
        content = path.read_text()
        assert 'requests.get(' not in content
        assert '/api/v1/query' not in content
        # Provider names in comments are not executable transport dependencies.
        # Keep checking executable tokens, imports and string literals.
        executable = ' '.join(
            token.string for token in generate_tokens(StringIO(content).readline) if token.type != COMMENT
        )
        assert 'prometheus' not in executable.lower() or path.name == 'observability.py'


def test_governance_workspace_keeps_independent_readiness_planes_out_of_posture() -> None:
    governance_presentation = (ROOT / 'app/artifact_registry/presentation_governance.py').read_text()
    wrapper = (ROOT / 'app/templates/artifact_registry/governance.html').read_text()
    workspace = (ROOT / 'app/templates/artifact_registry/partials/_governance_workspace.html').read_text()
    template = wrapper + workspace
    assert 'artifact_registry/partials/_governance_workspace.html' in wrapper

    for label in (
        'Provider Readiness',
        'Inventory Readiness',
        'Metrics Readiness',
        'Webhook Readiness',
    ):
        assert label not in governance_presentation

    assert 'Governance Data Snapshot' in template
    assert "'policies', 'Policies'" in template
    assert "'replication', 'Replication'" in template
    assert 'Sync Governance' in template
    assert 'Webhook Admission' not in template
    assert 'Generate Token' not in template
    assert 'Registry reconciliation' not in template


def test_governance_sync_uses_registered_jobexecution_boundary() -> None:
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    adapter = (ROOT / 'app/artifact_registry/governance_job_adapter.py').read_text()

    assert "job_key='artifact_registry.governance.sync'" in routes
    assert 'build_registry_governance_sync_state' in adapter
    assert "GOVERNANCE_SYNC_JOB_TYPE = 'artifact_registry_governance'" in adapter
    assert 'get_or_create_job_policy(GOVERNANCE_SYNC_JOB_KEY)' in adapter
    assert 'def governance_sync_status(public_id: str)' in routes
    live_state = (ROOT / 'app/templates/artifact_registry/partials/_governance_sync_live_state.html').read_text()
    assert "url_for('artifact_registry.governance_sync_status'" in live_state
    assert 'hx-trigger="every 1s"' in live_state
    assert 'progress_bar.job_progress' in live_state


def test_governance_latest_failed_refresh_never_looks_current() -> None:
    presenter = (ROOT / 'app/artifact_registry/presentation_governance.py').read_text()
    builder = presenter.split('def build_governance(', 1)[1]
    assert "if sync_state['label'] == 'Sync Failed':" in builder
    assert "'status': 'Refresh Failed' if summary['ready_count'] else 'Collection Failed'" in builder
    assert "'exceptions_label': 'Latest Sync Failed'" in builder
    assert "'snapshot_context': snapshot_context" in builder
    assert "'posture': posture" in builder


def test_read_only_governance_sync_poll_preserves_mutating_sync_permission() -> None:
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    sync = routes.split('def governance_sync() -> ResponseReturnValue:', 1)[0]
    poll = routes.split('def governance_sync_status(public_id: str) -> ResponseReturnValue:', 1)[0]
    assert "@artifact_registry_bp.post('/governance/sync')" in sync
    assert (
        "@permission_required('artifact_registry.sync')"
        in sync.rsplit("@artifact_registry_bp.post('/governance/sync')", 1)[1]
    )
    assert "@artifact_registry_bp.get('/governance/sync/status/<string:public_id>')" in poll
    assert (
        "@permission_required('artifact_registry.view')"
        in poll.rsplit("@artifact_registry_bp.get('/governance/sync/status/<string:public_id>')", 1)[1]
    )
    adapter = (ROOT / 'app/artifact_registry/governance_job_adapter.py').read_text()
    assert "latest_job.status == 'partially_succeeded'" in adapter
    assert "'Partial Evidence', 'warning'" in adapter


def test_governance_sync_matches_security_htmx_workspace_contract() -> None:
    from jinja2 import Environment

    security = (ROOT / 'app/templates/artifact_registry/partials/_security_workspace.html').read_text()
    governance = (ROOT / 'app/templates/artifact_registry/partials/_governance_workspace.html').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    live = (ROOT / 'app/templates/artifact_registry/partials/_governance_sync_live_state.html').read_text()
    wrapper = (ROOT / 'app/templates/artifact_registry/governance.html').read_text()

    Environment().parse(governance)
    Environment().parse(wrapper)

    # Use the approved Security evidence-operations UX without a new frontend
    # request pathway or duplicating registered JobExecution dispatch.
    for fragment in (
        'hx-disabled-elt="find button"',
        'hx-swap="outerHTML"',
        'name="csrf_token"',
        'class="{{ action_button.classes(\'primary\') }}"',
    ):
        assert fragment in security
        assert fragment in governance
    assert 'hx-post="{{ url_for(\'artifact_registry.governance_sync\') }}"' in governance
    assert 'hx-target="#artifact-registry-governance-workspace"' in governance
    assert 'name="tab" value="{{ governance.active_tab }}"' in governance
    assert 'name="page" value="{{ governance.pagination.page }}"' in governance
    # Preserve the hidden Rows value even when djLint wraps HTML attributes.
    assert re.search(
        r'<input[^>]*name="per_page"[^>]*'
        r'value="\{\{ governance\.pagination\.per_page \}\}"',
        governance,
    )
    assert 'governance.sync_state.is_active %}disabled' in governance
    assert 'Sync Governance' in governance
    assert 'artifact_registry.governance.sync' in governance

    # After a canonical execution terminates, refresh committed Governance
    # evidence, not live provider mutation or a second collection mechanism.
    assert 'hx-trigger="artifactRegistryGovernanceSyncFinished from:body"' in governance
    assert "url_for('artifact_registry.governance', tab=governance.active_tab" in governance
    assert 'hx-get="{{ url_for(' in governance
    assert 'artifactRegistryGovernanceSyncFinished' in routes
    assert 'hx-trigger="every 1s"' in live
    assert 'progress_bar.job_progress' in live
    assert 'registry.footer(' in governance
    assert 'hx_select' in governance

    # Like Security, the sync operations panel contains only JobExecution
    # state/scheduling facts; Governance coverage cards are a separate section.
    assert 'aria-label="Governance evidence coverage"' in governance
    assert (
        governance.index('Last Successful</p>')
        < governance.index('aria-label="Governance evidence coverage"')
        < governance.index('id="artifact-registry-governance-registry"')
    )
    assert 'governance.posture_cards' in governance

    get_handler = routes.split('def governance() -> ResponseReturnValue:', 1)[1].split(
        'def governance_sync() -> ResponseReturnValue:', 1
    )[0]
    post_handler = routes.split('def governance_sync() -> ResponseReturnValue:', 1)[1].split(
        'def governance_sync_status(public_id: str)', 1
    )[0]
    assert 'if is_htmx_request(request.headers)' in get_handler
    assert "'artifact_registry/partials/_governance_workspace.html'" in get_handler
    assert 'dispatch_registered_job(' in post_handler
    assert "job_key='artifact_registry.governance.sync'" in post_handler
    assert 'is_htmx = is_htmx_request(request.headers)' in post_handler
    assert 'queue_feedback=not is_htmx' in post_handler
    assert "'components/operational_toast.html'" in post_handler
    assert 'toast_oob=True' in post_handler
    assert 'governance=build_governance(' in post_handler
    assert 'active_tab=active_tab' in post_handler
    assert 'page=page' in post_handler
    assert 'per_page=per_page' in post_handler
    assert 'hx-post' not in live
    assert 'artifact_registry.inventory.sync' not in post_handler
    assert 'HarborClient' not in post_handler


def test_governance_evidence_tabs_are_badgeless_full_kaori_tables() -> None:
    from jinja2 import Environment

    workspace = (ROOT / 'app/templates/artifact_registry/partials/_governance_workspace.html').read_text()
    Environment().parse(workspace)

    start = workspace.index("content_tabs.render_links('registry-governance',")
    end = workspace.index('{% endif %}', start)
    evidence = workspace[start:end]
    # Tabs must reset to page 1 while preserving Rows; Jinja whitespace is cosmetic.
    for tab in ('policies', 'replication'):
        assert re.search(
            r"url_for\('artifact_registry\.governance',\s*"
            rf"tab='{tab}',\s*page=1,\s*per_page=governance\.pagination\.per_page\s*\)",
            evidence,
        )
    assert 'governance.project_count)' not in evidence
    assert 'governance.replication_count)' not in evidence
    assert "hx_target='#artifact-registry-governance-registry'" in evidence
    assert "hx_select='#artifact-registry-governance-registry'" in evidence
    assert "hx_push_url='true'" in evidence

    assert 'components/table.html' in workspace
    assert workspace.count("table_ui.table_classes('min-w-[") == 2
    assert workspace.count('table_ui.head_classes()') == 2
    assert workspace.count('table_ui.body_classes()') == 2
    assert workspace.count('table_ui.row_classes()') == 2
    assert workspace.count('table_ui.title_cell(') == 2
    assert workspace.count('table_ui.header_cell_classes()') == 12
    assert workspace.count('table_ui.cell_classes()') == 12
    assert workspace.count('<caption class="sr-only">Committed Registry') == 2
    assert 'Project Governance</h2>' not in evidence
    assert 'Resilience Evidence</p>' not in evidence
    assert 'class="border-b border-outline-subtle px-5 py-4"' not in evidence
    assert 'min-w-full divide-y divide-outline-subtle text-sm' not in evidence

    assert workspace.count("include 'components/states/_empty_state.html'") == 2
    assert 'No Policy Evidence Collected' in workspace
    assert 'governance.replication_empty.title' in workspace
    assert 'governance.replication_empty.description' in workspace
    presenter = (ROOT / 'app/artifact_registry/presentation_governance.py').read_text()
    assert 'No Replication Evidence Collected' in presenter
    assert 'row.retention_tone' in workspace and 'row.immutability_tone' in workspace
    assert "row.enabled is not none else 'Unknown'" in workspace
    assert 'row.destination_namespace' in workspace
    assert workspace.count("registry.footer('artifact_registry.governance'") == 2
    assert workspace.count('[5, 10, 25, 50]') == 2
    assert 'name="tab" value="{{ governance.active_tab }}"' in workspace
    assert 'artifactRegistryGovernanceSyncFinished from:body' in workspace


def test_governance_evidence_reuses_entire_canonical_table_workspace() -> None:
    from jinja2 import Environment

    workspace = (ROOT / 'app/templates/artifact_registry/partials/_governance_workspace.html').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    presentation = (ROOT / 'app/artifact_registry/presentation_governance.py').read_text()
    Environment().parse(workspace)

    evidence = workspace.split("content_tabs.render_links('registry-governance',", 1)[1]
    assert 'table_ui.inventory_block_header(' in evidence
    assert "'Project Policy Registry'" in evidence
    assert "'Replication Policy Registry'" in evidence
    assert 'title_extra=governance_result_badge' in evidence
    assert 'header_actions=governance_header_actions' in evidence
    assert "registry.clear_filters_link('artifact_registry.governance'," in evidence
    assert 'table_ui.inventory_filter_bar_classes()' in evidence
    assert "registry.filter_form('artifact_registry.governance'," in evidence
    assert "table_ui.search_field('q'," in evidence
    assert 'name="tab" value="{{ governance.active_tab }}"' in evidence
    for value in ('provider', 'retention', 'immutability', 'state'):
        assert f'name="{value}"' in evidence
        assert f'governance.filters.{value}' in evidence
    assert "'artifact-registry-governance-loading'" in evidence
    assert 'governance.pagination.total_items' in evidence
    assert 'No Policies Match Your Filters' in evidence
    assert 'No Replication Policies Match Your Filters' in evidence
    assert 'Project Governance</h2>' not in evidence
    assert 'Resilience Evidence</p>' not in evidence

    assert 'def _governance_filtered_query(' in presentation
    assert 'query = _governance_filtered_query(' in presentation
    assert 'items, pagination = paginate_query(query, page=page, per_page=per_page)' in presentation
    assert "'filter_query': filter_query" in presentation
    assert "'has_filters': filters_active" in presentation
    assert "'provider_options': [" in presentation
    assert 'func.lower(RegistryProject.name).like(pattern,' in presentation
    assert "'retention_label'" in presentation
    assert "'immutability_label'" in presentation
    # Persist the provider-observed tri-state instead of coercing None to Disabled.
    assert "'enabled': item.enabled" in presentation
    assert 'RegistryReplicationPolicy.enabled.is_(None)' in presentation
    assert "row.enabled is not none else 'Unknown'" in workspace
    assert "search=request.args.get('q', '', type=str)" in routes
    assert "search = request.form.get('q', '', type=str)" in routes
    assert 'provider=provider,' in routes
    assert 'retention=retention,' in routes
    assert 'immutability=immutability,' in routes
    assert 'state=state,' in routes
    assert 'governance.filters.search' in workspace
    assert workspace.count("registry.footer('artifact_registry.governance'") == 2
    assert workspace.count('[5, 10, 25, 50]') == 2
    assert 'artifactRegistryGovernanceSyncFinished from:body' in workspace


def test_governance_table_filter_and_pagination_use_active_sql_scope() -> None:
    presenter = (ROOT / 'app/artifact_registry/presentation_governance.py').read_text()
    query = presenter.split('def _governance_filtered_query(', 1)[1].split('def build_governance(', 1)[0]
    builder = presenter.split('def build_governance(', 1)[1]

    assert 'paginate_query(query, page=page, per_page=per_page)' in builder
    assert 'paginate_sequence(' not in builder
    assert '_filter_governance_rows(' not in presenter
    assert 'RegistryProject.integration_instance_id.in_(source_ids)' in query
    assert 'RegistryReplicationPolicy.integration_instance_id.in_(source_ids)' in query
    assert 'selected in source_ids' in query
    assert 'escaped = search.casefold().replace(' in query
    assert 'escape=' in query
    assert 'RegistryProjectGovernance.retention_status == retention' in query
    assert 'RegistryProjectGovernance.immutability_status == immutability' in query
    assert 'RegistryReplicationPolicy.enabled.is_(None)' in query
    assert 'func.lower(RegistryReplicationPolicy.name).like(pattern,' in query
    assert 'RegistryReplicationPolicy.name.asc()' in query
    assert 'RegistryProjectGovernance.observed_at.desc()' in query
    assert "row['provider_label']" not in query
    assert 'identity_by_id = {int(item.id): item for item in identities}' in builder
    assert "'provider_options': [" in builder
    assert "'id': int(identity.id)" in builder


def test_governance_inventory_commit_changes_invalidate_freshness() -> None:
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    from app.artifact_registry.presentation_governance import _governance_inventory_changed

    original = datetime(2026, 10, 12, tzinfo=UTC)
    state = SimpleNamespace(
        last_committed_at=original,
        metadata_json={'inventory_committed_at': original.isoformat()},
    )
    inventory = SimpleNamespace(last_committed_at=original)
    assert not _governance_inventory_changed(state, inventory)
    inventory.last_committed_at += timedelta(minutes=1)
    assert _governance_inventory_changed(state, inventory)
    state.metadata_json = {}
    assert _governance_inventory_changed(state, inventory)


def test_governance_coverage_and_evidence_follow_canonical_section_layout() -> None:
    from jinja2 import Environment

    workspace = (ROOT / 'app/templates/artifact_registry/partials/_governance_workspace.html').read_text()
    tabs = (ROOT / 'app/templates/components/content_tabs.html').read_text()
    intro = (ROOT / 'app/templates/components/section_intro.html').read_text()

    Environment().parse(workspace)
    # Both descriptive headings are plain section intros, not nested card headers.
    assert '{% import "components/section_intro.html" as section_intro %}' in workspace
    assert "section_intro.render('Governance Coverage'," in workspace
    assert "section_intro.render('Governance Evidence'," in workspace
    assert 'artifact-registry-governance-coverage-heading' in workspace
    assert 'artifact-registry-governance-evidence-heading' in workspace

    coverage = workspace.split("section_intro.render('Governance Coverage',", 1)[1].split(
        "section_intro.render('Governance Evidence',", 1
    )[0]
    # Human reference is the existing Tenant Estate grouped posture shell.
    # Governance alone adopts that composition; provider-committed state
    # labels remain visible rather than being replaced by icon-only tones.
    assert 'section_card.render(' in coverage
    assert "'Governance Evidence Estate'" in coverage
    assert "body_classes='p-0'" in coverage
    assert 'resource_posture_grid.render(coverage_metrics, columns=4, status_labels=coverage_status_labels)' in coverage
    assert 'class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"' not in coverage
    assert 'governance.posture_cards[0]' in coverage
    assert 'governance.posture_cards[1]' in coverage
    assert 'governance.posture_cards[2]' in coverage
    assert 'governance.posture_cards[3]' in coverage
    for name in ('policy_coverage', 'retention_coverage', 'immutability_coverage', 'replication_coverage'):
        for field in ('.label', '.value', '.detail', '.tone', '.status_label'):
            assert name + field in coverage
    for icon in ('shield-check', 'clock-3', 'lock-keyhole', 'git-compare-arrows'):
        assert icon in coverage

    posture = (ROOT / 'app/templates/components/resource_posture_grid.html').read_text()
    tenant = (ROOT / 'app/templates/kubernetes/tenant/overview.html').read_text()
    Environment().parse(posture)
    assert 'macro render(metrics, columns=3, status_labels=none)' in posture
    assert 'table_label.status_indicator_label(status_labels[loop.index0], tone)' in posture
    assert 'grid gap-px bg-outline-subtle' in posture
    assert '[overflow-wrap:anywhere]' in posture
    assert 'resource_posture_grid.render(estate_metrics, columns=5)' in tenant
    assert 'status_labels=' not in tenant

    # URL/HTMX-owned tabs reuse the shared content-tabs contract rather than
    # framed workspace tabs or bespoke client-side tab state.
    assert '{% import "components/content_tabs.html" as content_tabs %}' in workspace
    assert 'framed_workspace_tabs' not in workspace
    assert "content_tabs.render_links('registry-governance'," in workspace
    assert 'embedded=true' in workspace
    assert "hx_target='#artifact-registry-governance-registry'" in workspace
    assert "hx_select='#artifact-registry-governance-registry'" in workspace
    assert "hx_push_url='true'" in workspace
    assert "hx_target='#artifact-registry-governance-registry'" in workspace
    assert "url_for('artifact_registry.governance', tab='policies', page=1" in workspace
    assert "url_for('artifact_registry.governance', tab='replication', page=1" in workspace
    assert 'macro render_links(' in tabs
    assert 'macro render(' in intro

    # Existing committed policy/replication views, active row page sizes and
    # independent sync progress must not be affected by the presentation change.
    assert 'id="artifact-registry-governance-registry"' in workspace
    assert "governance.active_tab == 'policies'" in workspace
    assert 'governance.rows' in workspace
    assert workspace.count("registry.footer('artifact_registry.governance'") == 2
    assert workspace.count('[5, 10, 25, 50]') == 2
    assert 'artifactRegistryGovernanceSyncFinished from:body' in workspace
    assert "url_for('artifact_registry.governance_sync')" in workspace


def test_registry_guidance_copy_keeps_provider_and_committed_evidence_authority() -> None:
    harbor = (ROOT / 'app/templates/integrations/registry/providers/harbor/index.html').read_text(encoding='utf-8')
    governance = (ROOT / 'app/artifact_registry/presentation_governance.py').read_text(encoding='utf-8')
    assert (
        'KAORI uses committed Registry inventory and validated Metrics Source bindings for operational metrics.'
        in harbor
    )
    assert 'Harbor owns repositories, artifacts, policies, and runtime;' in harbor
    assert 'KAORI validates, normalizes, correlates, and commits evidence.' in harbor
    assert 'Committed project retention and immutability evidence.' in governance
