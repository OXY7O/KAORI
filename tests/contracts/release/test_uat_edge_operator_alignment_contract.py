from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UAT_WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-staging-host.yml'
EDGE_README = ROOT / 'example' / 'shared-edge' / 'README.md'


def test_letsencrypt_configuration_is_not_part_of_kaori_uat_delivery() -> None:
    uat = UAT_WORKFLOW.read_text(encoding='utf-8')

    assert 'KAORI_LETSENCRYPT_EMAIL' not in uat
    assert 'EDGE_LETSENCRYPT_EMAIL' not in uat
    assert 'deploy/nginx' not in uat
    assert 'example/shared-edge' not in uat


def test_standalone_edge_runbook_documents_independent_multi_application_publication() -> None:
    readme = EDGE_README.read_text(encoding='utf-8')

    required = (
        'optional reference implementation',
        'edge-public',
        '/opt/shared-edge',
        'publish-container.sh',
        'kaori-cutover-example.sh',
        'kaori.cloud',
        'auto.kaori.cloud',
        'n8n is **not part of KAORI**',
        'unknown Host/SNI',
        'Certbot',
        'Docker socket',
    )
    for marker in required:
        assert marker in readme
