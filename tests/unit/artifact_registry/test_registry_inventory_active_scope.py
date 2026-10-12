from __future__ import annotations

from pathlib import Path

import pytest

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


def test_malformed_registry_inventory_source_filter_does_not_expand_scope() -> None:
    from flask import Flask
    from werkzeug.exceptions import NotFound

    from app.artifact_registry.routes import _inventory_source_id

    flask = Flask('registry-inventory-scope-test')
    for raw in ('?source_id=abc', '?source_id=-2', '?source_id=0', '?source_id=3.1'):
        with flask.test_request_context('/artifact-registry/inventory/artifacts' + raw):
            with pytest.raises(NotFound):
                _inventory_source_id()
    for raw, expected in (('', None), ('?source_id=', None), ('?source_id=3', 3)):
        with flask.test_request_context('/artifact-registry/inventory/projects' + raw):
            assert _inventory_source_id() == expected


def test_detail_scope_predicate_is_shared_across_resources() -> None:
    source = (Path(__file__).resolve().parents[3] / 'app/artifact_registry/presentation_inventory.py').read_text()
    assert source.count('_inventory_detail_in_active_committed_scope(') == 4
    assert "IntegrationInstance.enabled.is_(True)" in source
    assert 'RegistryCollectionState.last_committed_at.is_not(None)' in source
