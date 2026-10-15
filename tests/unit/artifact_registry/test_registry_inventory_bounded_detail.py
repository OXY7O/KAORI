from __future__ import annotations

from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[3] / 'app/artifact_registry/presentation_inventory.py').read_text(
    encoding='utf-8'
)


def _section(name: str, next_name: str | None = None) -> str:
    part = SOURCE.split(f'def {name}(', 1)[1]
    return part.split(f'def {next_name}(', 1)[0] if next_name else part


def test_project_modal_limits_sql_repository_preview_to_25_rows() -> None:
    section = _section('build_inventory_project_detail', '_inventory_detail_provider_context')
    assert 'RegistryRepository.query.filter_by(project_id=project.id).count()' in section
    assert '.limit(25)' in section
    assert '.all()' in section
    assert 'project.repositories' not in section
    assert "'repository_truncated': repository_total > 25" in section


def test_repository_modal_limits_sql_artifact_and_tag_previews() -> None:
    section = _section('build_inventory_repository_detail', 'build_inventory_artifact_detail')
    assert 'RegistryArtifact.query.filter_by(repository_id=repository.id).count()' in section
    assert 'RegistryArtifact.digest.asc()' in section
    assert '.limit(25)' in section
    assert '.all()' in section
    assert 'func.row_number().over(' in section
    assert 'tagged.c.tag_rank <= 3' in section
    assert 'RegistryTag.artifact_id.in_(artifact_ids)' in section
    assert 'repository.artifacts' not in section
    assert "'artifact_truncated': artifact_total > 25" in section


def test_artifact_modal_limits_tag_rows_without_loading_all_tags() -> None:
    section = _section('build_inventory_artifact_detail')
    assert 'RegistryTag.query.filter_by(artifact_id=artifact.id).count()' in section
    assert 'func.lower(RegistryTag.name).asc()' in section
    assert '.limit(25)' in section
    assert '.all()' in section
    assert 'artifact.tags' not in section
    assert "'tag_truncated': tag_total > 25" in section


def test_detail_modal_contract_and_provider_boundaries_are_unchanged() -> None:
    for name in (
        'build_inventory_project_detail',
        'build_inventory_repository_detail',
        'build_inventory_artifact_detail',
    ):
        assert f'def {name}(' in SOURCE
    assert '_inventory_detail_provider_context(' in SOURCE
    assert 'build_client' not in SOURCE
