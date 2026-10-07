from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_registry_inventory_is_provider_neutral_and_digest_oriented() -> None:
    models = (ROOT / 'app/models/registry.py').read_text()
    assert 'class RegistryProject' in models
    assert 'class RegistryRepository' in models
    assert 'class RegistryArtifact' in models
    assert 'class RegistryTag' in models
    assert "UniqueConstraint('repository_id', 'digest'" in models
    assert 'HarborProject' not in models
    assert 'HarborRepository' not in models
    assert 'HarborArtifact' not in models


def test_registry_operational_pages_read_committed_state() -> None:
    presentation = (ROOT / 'app/artifact_registry/presentation_inventory.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    assert 'RegistryProject.query' in presentation
    assert 'RegistryArtifact.query' in presentation
    assert 'build_client' not in presentation
    assert 'requests.' not in routes


def test_harbor_is_collector_not_operational_page_authority() -> None:
    sync = (ROOT / 'app/artifact_registry/sync.py').read_text()
    collector = (ROOT / 'app/integrations/registry/providers/harbor/inventory.py').read_text()
    client = (ROOT / 'app/integrations/registry/providers/harbor/client.py').read_text()

    assert 'get_registry_collector' in sync
    assert 'commit_registry_inventory' in sync
    assert 'HarborInstance' not in sync
    assert 'collect_harbor_inventory' in collector
    assert 'RegistryInventoryEvidence' in collector
    assert 'list_all_artifacts' in client
    assert 'get_vulnerability_report' not in collector
    assert 'with_scan_overview=True' not in collector
    assert 'with_sbom_overview=True' not in collector
    assert 'with_signature=True' not in collector
    assert 'with_immutable_status=True' not in collector


def test_registry_inventory_sync_uses_operational_read_contract_eligibility() -> None:
    eligibility = (ROOT / 'app/artifact_registry/eligibility.py').read_text()
    sync = (ROOT / 'app/artifact_registry/sync.py').read_text()
    sync_jobs = (ROOT / 'app/artifact_registry/sync_jobs.py').read_text()

    assert "normalized_readiness == 'ready'" in eligibility
    assert "normalized_readiness == 'degraded'" in eligibility
    assert "normalized_compatibility == 'compatible_with_warnings'" in eligibility
    assert (
        'unverified_version'
        not in eligibility.split('def inventory_read_contract_eligible', 1)[1].split(
            'def registry_inventory_eligibility', 1
        )[0]
    )
    assert 'registry_inventory_eligibility(identity, provider_record=provider_record)' in sync
    assert "identity.readiness_status != 'ready'" not in sync
    assert 'registry_inventory_eligibility(identity)' in sync_jobs
    assert "IntegrationInstance.readiness_status == 'ready'" not in sync_jobs


def test_global_sync_all_inventory_includes_artifact_registry() -> None:
    routes = (ROOT / 'app/platform_operations/jobs/routes.py').read_text()
    navbar = (ROOT / 'app/templates/components/navigation/navbar.html').read_text()

    assert "current_user.has_permission('artifact_registry.sync')" in routes
    assert "job_keys.append('artifact_registry.inventory.sync')" in routes
    assert ("can_sync_artifact_registry_inventory = current_user.has_permission('artifact_registry.sync')") in navbar
    assert (
        'can_sync_kubernetes_inventory or can_sync_object_storage_inventory or can_sync_artifact_registry_inventory'
    ) in navbar


def test_registry_inventory_worker_registration_matches_dispatch_contract() -> None:
    config = (ROOT / 'app/config/default.py').read_text()
    sync_jobs = (ROOT / 'app/artifact_registry/sync_jobs.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()

    assert "'app.artifact_registry.tasks'," in config
    assert "'app.artifact_registry.tasks.sync_all_registry': {" in config
    registry_route = config.split(
        "'app.artifact_registry.tasks.sync_all_registry': {",
        1,
    )[1].split('},', 1)[0]
    assert "'queue': 'inventory'" in registry_route

    assert 'JobDispatchOptions' in sync_jobs
    assert sync_jobs.count('require_registered_worker=True') >= 2
    assert 'JobWorkerUnavailable' in routes
    assert 'Artifact Registry Worker Unavailable' in routes


def test_registry_inventory_worker_does_not_cross_into_other_registry_workstreams() -> None:
    task = (ROOT / 'app/artifact_registry/tasks.py').read_text()
    sync = (ROOT / 'app/artifact_registry/sync.py').read_text()

    assert 'sync_registry_governance' not in task
    assert 'refresh_registry_workload_bindings' not in sync


def test_registry_inventory_reports_live_provider_progress() -> None:
    collectors = (ROOT / 'app/artifact_registry/collectors.py').read_text()
    harbor = (ROOT / 'app/integrations/registry/providers/harbor/inventory.py').read_text()
    sync = (ROOT / 'app/artifact_registry/sync.py').read_text()
    task = (ROOT / 'app/artifact_registry/tasks.py').read_text()

    assert 'InventoryProgressCallback' in collectors
    assert 'collect_with_progress' in collectors
    assert 'progress_callback' in harbor
    assert "progress_callback(0, 0, 'Project Discovery')" in harbor
    assert 'repository_processed' in harbor
    assert 'collect_with_progress(provider_record, progress_callback)' in sync
    assert 'report_inventory_progress' in task
    assert "self.update_state(state='PROGRESS'" in task


def test_registry_inventory_reconciles_stable_rows_without_erasing_downstream_evidence() -> None:
    sync = (ROOT / 'app/artifact_registry/sync.py').read_text()

    assert 'selectinload(RegistryProject.repositories)' in sync
    assert 'existing_projects.pop(record.name, None)' in sync
    assert 'existing.pop(record.digest, None)' in sync
    assert 'RegistryProject.query.filter_by(integration_instance_id=integration_instance_id).delete' not in sync

    reconcile_artifacts = sync.split('def _reconcile_artifacts', 1)[1].split(
        'def _reconcile_repositories',
        1,
    )[0]
    assert 'artifact.scan_status =' not in reconcile_artifacts
    assert 'artifact.vulnerability_summary =' not in reconcile_artifacts
    assert 'artifact.signature_status =' not in reconcile_artifacts
    assert 'artifact.sbom_status =' not in reconcile_artifacts


def test_registry_inventory_reuses_canonical_inventory_workspace_primitives() -> None:
    overview_template = (ROOT / 'app/templates/artifact_registry/partials/_inventory_overview.html').read_text()
    resource_template = (ROOT / 'app/templates/artifact_registry/partials/_inventory_workspace.html').read_text()
    presentation = (ROOT / 'app/artifact_registry/presentation_inventory.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    navigation = (ROOT / 'app/common/workspace_navigation_catalog.py').read_text()
    navigation_service = (ROOT / 'app/common/workspace_navigation.py').read_text()

    assert 'components/snapshot_context_bar.html' in overview_template
    assert 'components/inventory_asset_card.html' in overview_template
    assert 'components/section_intro.html' in overview_template
    assert 'components/operational_callout.html' in overview_template
    assert 'components/operational_section_card.html' not in overview_template
    assert 'Fleet Inventory Posture' in overview_template
    assert 'Registry Asset Catalog' in overview_template
    assert 'Inventory Assets' not in overview_template
    assert 'inventory.fleet_readings' in overview_template
    assert "variant='neutral'" in overview_template
    assert 'url_for(asset.endpoint)' in overview_template
    assert 'components/snapshot_context_bar.html' in resource_template
    assert 'components/operational_section_card.html' in resource_template
    assert 'components/resource_posture_grid.html' in resource_template
    assert 'inventory.resource_posture_title' in resource_template
    assert 'inventory.resource_posture_intro' in resource_template
    assert 'inventory.resource_posture_description' in resource_template
    assert 'inventory.resource_posture_metrics' in resource_template
    assert (
        "inventory.resource == 'projects'"
        not in resource_template.split(
            'registry-resource-posture-heading',
            1,
        )[1].split('registry-inventory-records-heading', 1)[0]
    )
    assert 'components/table.html' in resource_template
    assert 'components/states/_empty_state.html' in resource_template
    assert 'artifact-registry-inventory-content' in resource_template
    assert '[5, 10, 25, 50]' in resource_template
    assert 'table_ui.table_classes' in resource_template
    assert 'min-w-full divide-y divide-outline-subtle' not in resource_template
    assert 'inventory.resource_endpoint' in resource_template
    assert 'name="resource"' not in resource_template
    assert "@artifact_registry_bp.get('/inventory/projects')" in routes
    assert "@artifact_registry_bp.get('/inventory/repositories')" in routes
    assert "@artifact_registry_bp.get('/inventory/artifacts')" in routes
    assert "request.args.get('resource'" not in routes
    assert "'artifact_registry_inventory': (" in navigation
    assert "'artifact_registry.inventory_projects'" in navigation
    assert "'artifact_registry.inventory_repositories'" in navigation
    assert "'artifact_registry.inventory_artifacts'" in navigation
    assert "return 'artifact_registry_inventory'" in navigation_service
    assert "'artifact_registry.inventory_projects': 'projects'" in navigation_service
    assert "'artifact_registry.inventory_repositories': 'repositories'" in navigation_service
    assert "'artifact_registry.inventory_artifacts': 'artifacts'" in navigation_service
    assert 'def build_inventory_overview()' in presentation
    assert 'def _inventory_fleet_readings(overview: dict[str, Any])' in presentation
    assert "'fleet_readings': _inventory_fleet_readings(overview)" in presentation
    assert "'asset_catalog': list(resource_catalog.values())" in presentation
    assert "'resource_endpoint': selected_resource['endpoint']" in presentation
    assert 'def _inventory_resource_posture_metrics(' in presentation
    assert "'resource_posture_metrics': resource_posture_metrics" in presentation
    assert "'Project Inventory Posture'" in presentation
    assert "'Repository Inventory Posture'" in presentation
    assert "'Artifact Inventory Posture'" in presentation
    assert "'Visibility Not Observed'" in presentation
    assert "'Pull Counts Observed'" in presentation
    assert "'Tagged Artifacts'" in presentation
    assert "'Untagged Artifacts'" in presentation
    assert "row['provider_name']" in presentation


def test_registry_inventory_overview_restores_asset_counts_from_existing_kpis() -> None:
    presentation = (ROOT / 'app/artifact_registry/presentation_inventory.py').read_text()

    inventory_base = presentation.split('def _inventory_base_context()', 1)[1].split(
        'def build_inventory_overview()',
        1,
    )[0]
    assert 'counts = _overview_kpi_values(None)' in inventory_base
    assert "'project_count': counts['projects']" in inventory_base
    assert "'repository_count': counts['repositories']" in inventory_base
    assert "'artifact_count': counts['artifacts']" in inventory_base


def test_registry_project_inventory_reuses_canonical_filters_and_detail_modal() -> None:
    presentation = (ROOT / 'app/artifact_registry/presentation_inventory.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    workspace = (ROOT / 'app/templates/artifact_registry/partials/_inventory_workspace.html').read_text()
    page = (ROOT / 'app/templates/artifact_registry/inventory_resource.html').read_text()
    detail = (ROOT / 'app/templates/artifact_registry/partials/_inventory_project_detail.html').read_text()

    assert 'table_ui.inventory_filter_bar_classes()' in workspace
    assert 'id="artifact-registry-inventory-table"' in workspace
    assert "target='#artifact-registry-inventory-table'" in workspace
    assert "'artifact-registry-inventory-table'," in workspace
    assert 'name="source_id"' in workspace
    assert 'name="environment"' in workspace
    assert 'name="visibility"' in workspace
    assert 'id="artifact-registry-inventory-source"' in workspace
    assert 'id="artifact-registry-inventory-environment"' in workspace
    assert "'source_id': source_id" in presentation
    assert "'environment': environment_value" in presentation
    assert 'or source_id is not None' in presentation
    assert 'or environment_value' in presentation
    assert "copyable=true, class_name='lg:col-span-2'" not in detail
    assert 'resource_detail_modal.detail_button' in workspace
    assert 'resource_detail_modal.inventory_host' in page
    assert "@artifact_registry_bp.get('/inventory/projects/<int:project_id>/details')" in routes
    assert 'def build_inventory_project_detail(project_id: int)' in presentation
    assert 'RegistryProject.query.options' in presentation
    assert 'HarborClient' not in presentation
    assert 'components/details/_detail_content.html' in detail
    assert 'Committed Snapshot Boundary' in detail


def test_registry_repository_and_artifact_inventory_reuse_full_workspace_detail_modal() -> None:
    presentation = (ROOT / 'app/artifact_registry/presentation_inventory.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    workspace = (ROOT / 'app/templates/artifact_registry/partials/_inventory_workspace.html').read_text()
    page = (ROOT / 'app/templates/artifact_registry/inventory_resource.html').read_text()
    repository_detail = (
        ROOT / 'app/templates/artifact_registry/partials/_inventory_repository_detail.html'
    ).read_text()
    artifact_detail = (ROOT / 'app/templates/artifact_registry/partials/_inventory_artifact_detail.html').read_text()

    assert 'def build_inventory_repository_detail(repository_id: int)' in presentation
    assert 'def build_inventory_artifact_detail(artifact_id: int)' in presentation
    assert 'build_client' not in presentation
    assert 'RegistryRepository.query.options(' in presentation
    assert 'RegistryArtifact.query.options(' in presentation

    assert "@artifact_registry_bp.get('/inventory/repositories/<int:repository_id>/details')" in routes
    assert "@artifact_registry_bp.get('/inventory/artifacts/<int:artifact_id>/details')" in routes
    assert 'build_inventory_repository_detail(repository_id)' in routes
    assert 'build_inventory_artifact_detail(artifact_id)' in routes

    assert "url_for('artifact_registry.inventory_repository_details'" in workspace
    assert "url_for('artifact_registry.inventory_artifact_details'" in workspace
    assert workspace.count("label='View More'") >= 2
    assert "url_for('artifact_registry.inventory_repository_details', repository_id=0)" in page
    assert "url_for('artifact_registry.inventory_artifact_details', artifact_id=0)" in page
    assert page.count('resource_detail_modal.inventory_host(') >= 3

    for detail in (repository_detail, artifact_detail):
        assert 'components/details/_detail_content.html' in detail
        assert 'data-kaori-detail-variant="full-workspace-modal"' in detail
        assert 'data-kaori-detail-density="unified-resource-sheet"' in detail
        assert 'detail.inspector_summary_strip' in detail
        assert 'detail.resource_sheet()' in detail
        assert 'Committed Snapshot Boundary' in detail
        assert 'no live provider request' in detail

    assert 'Artifact Coverage' in repository_detail
    assert 'repository.artifact_preview' in repository_detail
    assert 'Showing the first 25 artifacts.' in repository_detail
    assert 'Artifact Identity' in artifact_detail
    assert 'Tag References' in artifact_detail
    assert 'artifact.tag_preview' in artifact_detail
    assert "copyable=true, class_name='lg:col-span-2'" not in repository_detail
    assert (
        "detail.inventory_technical_row('Provider Native ID', artifact.provider_native_id, copyable=true)"
        not in artifact_detail
    )
    assert "detail.inventory_technical_row('Digest', artifact.digest, copyable=true" in artifact_detail
    assert 'artifact.scan_status' not in artifact_detail
    assert 'artifact.vulnerability_summary' not in artifact_detail
    assert 'artifact.signature_status' not in artifact_detail
    assert 'artifact.sbom_status' not in artifact_detail
    assert "detail.inventory_section(\n                    'Security'" not in artifact_detail
