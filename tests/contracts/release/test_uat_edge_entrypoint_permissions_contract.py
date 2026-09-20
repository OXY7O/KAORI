from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UAT_WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-staging-host.yml'
EDGE_WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-shared-edge.yml'


def test_kaori_uat_keeps_server_scripts_private_and_does_not_ship_edge_runtime() -> None:
    source = UAT_WORKFLOW.read_text(encoding='utf-8')

    assert 'chmod 700 -- "$remote_release"/deploy/server/*.sh' in source
    assert 'deploy/nginx' not in source
    assert 'deploy/edge' not in source


def test_shared_edge_workflow_installs_container_readable_edge_entrypoints() -> None:
    source = EDGE_WORKFLOW.read_text(encoding='utf-8')

    assert 'scp "${scp_opts[@]}" -r deploy/edge' in source
    assert 'chmod 755 -- "$remote_release"/deploy/edge/*.sh' in source
    assert 'deploy/server/deploy.sh' not in source
