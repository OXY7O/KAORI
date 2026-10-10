from pathlib import Path

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
        assert 'prometheus' not in content.lower() or path.name == 'observability.py'


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
    for fragment in ('hx-disabled-elt="find button"', 'hx-swap="outerHTML"',
                     'name="csrf_token"', 'class="{{ action_button.classes(\'primary\') }}"'):
        assert fragment in security
        assert fragment in governance
    assert "hx-post=\"{{ url_for('artifact_registry.governance_sync') }}\"" in governance
    assert 'hx-target="#artifact-registry-governance-workspace"' in governance
    assert 'name="tab" value="{{ governance.active_tab }}"' in governance
    assert 'name="page" value="{{ governance.pagination.page }}"' in governance
    assert 'name="per_page" value="{{ governance.pagination.per_page }}"' in governance
    assert "governance.sync_state.is_active %}disabled" in governance
    assert "Sync Governance" in governance
    assert "artifact_registry.governance.sync" in governance

    # After a canonical execution terminates, refresh committed Governance
    # evidence, not live provider mutation or a second collection mechanism.
    assert 'hx-trigger="artifactRegistryGovernanceSyncFinished from:body"' in governance
    assert "url_for('artifact_registry.governance', tab=governance.active_tab" in governance
    assert 'hx-get="{{ url_for(' in governance
    assert 'artifactRegistryGovernanceSyncFinished' in routes
    assert "hx-trigger=\"every 1s\"" in live
    assert "progress_bar.job_progress" in live
    assert "registry.footer(" in governance
    assert "hx_select" in governance

    # Like Security, the sync operations panel contains only JobExecution
    # state/scheduling facts; Governance coverage cards are a separate section.
    assert 'aria-label="Governance evidence coverage"' in governance
    assert governance.index('Last Successful</p>') < governance.index(
        'aria-label="Governance evidence coverage"'
    ) < governance.index('id="artifact-registry-governance-registry"')
    assert "governance.posture_cards" in governance

    get_handler = routes.split("def governance() -> ResponseReturnValue:", 1)[1].split(
        "def governance_sync() -> ResponseReturnValue:", 1
    )[0]
    post_handler = routes.split("def governance_sync() -> ResponseReturnValue:", 1)[1].split(
        "def governance_sync_status(public_id: str)", 1
    )[0]
    assert "if is_htmx_request(request.headers)" in get_handler
    assert "'artifact_registry/partials/_governance_workspace.html'" in get_handler
    assert "dispatch_registered_job(" in post_handler
    assert "job_key='artifact_registry.governance.sync'" in post_handler
    assert "is_htmx = is_htmx_request(request.headers)" in post_handler
    assert "queue_feedback=not is_htmx" in post_handler
    assert "'components/operational_toast.html'" in post_handler
    assert "toast_oob=True" in post_handler
    assert "governance=build_governance(" in post_handler
    assert "active_tab=active_tab" in post_handler
    assert "page=page" in post_handler
    assert "per_page=per_page" in post_handler
    assert 'hx-post' not in live
    assert "artifact_registry.inventory.sync" not in post_handler
    assert "HarborClient" not in post_handler



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
    # KPI cards match standalone Security/Runtime/Analytics summary geometry,
    # without a second outer border or surface frame.
    assert 'class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"' in coverage
    assert 'flex h-full min-w-0 flex-col rounded-xl border border-outline-default bg-surface-card p-4 shadow-sm' in coverage
    assert 'class="grid gap-3 bg-surface-subtle p-4 sm:grid-cols-2 xl:grid-cols-4"' not in coverage
    assert 'class="{{ section_card.shell_classes() }}"' not in coverage
    assert 'for item in governance.posture_cards' in coverage
    assert 'item.status_label, item.tone' in coverage
    assert "item.label" in coverage and "item.value" in coverage and "item.detail" in coverage
    assert "min-w-0 rounded-lg border border-outline-subtle" in coverage

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
    assert "macro render_links(" in tabs
    assert "macro render(" in intro

    # Existing committed policy/replication views, active row page sizes and
    # independent sync progress must not be affected by the presentation change.
    assert 'id="artifact-registry-governance-registry"' in workspace
    assert 'governance.active_tab == \'policies\'' in workspace
    assert 'governance.rows' in workspace
    assert workspace.count("registry.footer('artifact_registry.governance'") == 2
    assert workspace.count('[5, 10, 25, 50]') == 2
    assert "artifactRegistryGovernanceSyncFinished from:body" in workspace
    assert "url_for('artifact_registry.governance_sync')" in workspace
