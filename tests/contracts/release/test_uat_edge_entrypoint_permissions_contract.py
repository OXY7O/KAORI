from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UAT_WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-staging-host.yml'
EDGE_EXAMPLE = ROOT / 'example' / 'shared-edge'


def test_kaori_uat_keeps_server_scripts_private_and_does_not_ship_public_edge_runtime() -> None:
    source = UAT_WORKFLOW.read_text(encoding='utf-8')

    assert 'chmod 700 -- "$remote_release"/deploy/server/*.sh' in source
    assert 'deploy/nginx' not in source
    assert 'deploy/edge' not in source
    assert 'example/shared-edge' not in source


def test_standalone_edge_entrypoints_are_kept_only_in_the_example_surface() -> None:
    assert (EDGE_EXAMPLE / 'nginx-entrypoint.sh').is_file()
    assert (EDGE_EXAMPLE / 'certbot-entrypoint.sh').is_file()
    assert not (ROOT / '.github' / 'workflows' / 'deploy-shared-edge.yml').exists()
