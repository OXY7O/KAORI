from __future__ import annotations

from pathlib import Path

from app.artifact_registry import presentation_inventory


def test_inventory_scope_is_restricted_before_resource_filter_and_pagination() -> None:
    source = (Path(__file__).resolve().parents[3] / 'app/artifact_registry/presentation_inventory.py').read_text()
    assert "_overview_inventory_kpi_evidence(scoped_providers, states)" in source
    assert "'committed_provider_ids': committed_provider_ids" in source
    assert "_inventory_rows(resource, context['committed_provider_ids'])" in source
    rows = source.split('def _inventory_rows(', 1)[1].split('def _inventory_filter_options(', 1)[0]
    assert rows.count('RegistryProject.integration_instance_id.in_(committed_provider_ids)') >= 1
    fleet = source.split('def _inventory_fleet_readings(', 1)[1].split('def _inventory_base_context(', 1)[0]
    assert 'scoped_projects = RegistryProject.query.filter(' in fleet
    assert 'RegistryProject.integration_instance_id.in_(committed_provider_ids)' in fleet


def test_committed_empty_has_no_visibility_evidence() -> None:
    # The count scope is never widened to retired/disabled Registry records.
    source = (Path(__file__).resolve().parents[3] / 'app/artifact_registry/presentation_inventory.py').read_text()
    assert 'visibility_observed = scoped_projects.filter(' in source
    assert 'public_projects = scoped_projects.filter(' in source
    assert 'project_count == 0' in source
