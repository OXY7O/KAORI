from types import SimpleNamespace

from app.reports.export.payloads.artifact_registry_inventory import _inventory_rows
from app.reports.export.xlsx.standard import get_inventory_workbook_profile


def test_inventory_retains_empty_project_and_repository_with_real_artifact_rows() -> None:
    artifact = SimpleNamespace(
        digest='sha256:a', vulnerability_summary={'critical': 1},
        tags=[SimpleNamespace(name='v1')], artifact_type='image',
        media_type='application/vnd.oci.image.manifest.v1+json',
        size_bytes=1048576, scan_status='scanned', signature_status='signed',
        sbom_status='available', push_time=None, pull_time=None, observed_at=None,
    )
    projects = [
        SimpleNamespace(name='empty-project', repositories=[], observed_at=None),
        SimpleNamespace(
            name='filled-project',
            repositories=[
                SimpleNamespace(name='empty-repository', artifacts=[], observed_at=None),
                SimpleNamespace(name='service', artifacts=[artifact], observed_at=None),
            ],
        ),
    ]
    instance = SimpleNamespace(name='registry', environment='uat')
    rows = _inventory_rows(instance, projects)
    assert [row['record_type'] for row in rows] == ['project', 'repository', 'artifact']
    assert rows[0]['project'] == 'empty-project'
    assert rows[0]['repository'] is None and rows[0]['digest'] is None
    assert rows[1]['repository'] == 'empty-repository' and rows[1]['digest'] is None
    assert rows[2]['digest'] == 'sha256:a'
    assert rows[2]['critical_findings'] == 1
    assert 'scan_status' not in rows[0]
    assert 'size_mib' not in rows[1]


def test_inventory_artifact_kpi_does_not_count_empty_container_identities() -> None:
    profile = get_inventory_workbook_profile('artifact_registry_inventory')
    metric = profile.overview_metrics[0]
    assert metric.label == 'Artifacts'
    assert metric.aggregation == 'count'
    assert metric.key == 'record_type'
    assert metric.match_values == ('artifact',)
    assert profile.identity_columns == ('registry', 'environment', 'project', 'repository', 'digest')
    assert 'record_type' in {column.key for column in profile.columns}
