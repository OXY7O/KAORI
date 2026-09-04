from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-uat-vps.yml'


def test_uat_edge_entrypoints_are_container_readable_without_relaxing_vps_scripts() -> None:
    source = WORKFLOW.read_text(encoding='utf-8')

    assert 'chmod 700 -- "$remote_release"/deploy/vps/*.sh' in source
    assert 'chmod 755 -- "$remote_release"/deploy/nginx/*.sh' in source
    assert 'chmod 700 -- "$remote_release"/deploy/nginx/*.sh' not in source
