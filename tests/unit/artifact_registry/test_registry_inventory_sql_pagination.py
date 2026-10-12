from __future__ import annotations

from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[3] / 'app/artifact_registry/presentation_inventory.py'
).read_text(encoding='utf-8')


def test_all_inventory_resource_lists_are_sql_paginated_before_hydration() -> None:
    rows = SOURCE.split('def _inventory_rows(', 1)[1].split('def _inventory_filter_options(', 1)[0]
    assert '.all()' not in rows
    assert 'joinedload(' not in rows
    assert 'IntegrationInstance.id == RegistryProject.integration_instance_id' in rows

    builder = SOURCE.split('def build_inventory(', 1)[1].split('def build_inventory_project_detail(', 1)[0]
    assert '_inventory_search_filter(filtered_query, resource, search_value)' in builder
    assert 'paginate_query(filtered_query, page=page, per_page=per_page)' in builder
    assert "items, pagination = paginate_query(" in builder
    assert 'paged = _decorate_inventory_provider_provenance([row_builder(item) for item in items])' in builder
    assert 'paginate_sequence(' not in builder
    assert 'filtered = [row for row in rows' not in builder


def test_artifact_tag_search_deduplicates_by_existing_correlated_relation() -> None:
    text = SOURCE.split('def _inventory_search_filter(', 1)[1].split('def _inventory_resource_posture_metrics(', 1)[0]
    assert "RegistryArtifact.tags.any(RegistryTag.name.ilike(" in text
    assert 'join(RegistryTag)' not in text
    assert "replace('%', '\\\\%')" in text or "replace('%', '\\%')" in text


def test_posture_and_selectors_are_sql_aggregated_over_full_unfiltered_scope() -> None:
    builder = SOURCE.split('def build_inventory(', 1)[1].split('def build_inventory_project_detail(', 1)[0]
    assert builder.index('_inventory_resource_posture_metrics(resource, scoped_query)') < builder.index('_inventory_scope_filter(')
    posture = SOURCE.split('def _inventory_resource_posture_metrics(', 1)[1].split('def _inventory_posture_copy(', 1)[0]
    assert 'query.order_by(None).count()' in posture
    assert 'func.count(func.distinct(RegistryProject.integration_instance_id))' in posture
    assert 'RegistryArtifact.tags.any()' in posture


def test_only_one_page_loads_artifact_tags_and_optional_child_counts() -> None:
    builder = SOURCE.split('def build_inventory(', 1)[1].split('def build_inventory_project_detail(', 1)[0]
    assert 'filtered_query.options(selectinload(RegistryArtifact.tags))' in builder
    rows = SOURCE.split('def _project_row(', 1)[1].split('def _decorate_inventory_provider_provenance(', 1)[0]
    assert 'len(item.repositories)' not in rows
    assert 'len(item.artifacts)' not in rows
