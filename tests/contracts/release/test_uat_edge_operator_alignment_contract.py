from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UAT_WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-staging-host.yml'
EDGE_WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-shared-edge.yml'
EDGE_README = ROOT / 'deploy' / 'edge' / 'README.md'


def test_letsencrypt_bootstrap_belongs_only_to_shared_edge_delivery() -> None:
    uat = UAT_WORKFLOW.read_text(encoding='utf-8')
    edge = EDGE_WORKFLOW.read_text(encoding='utf-8')

    assert 'KAORI_LETSENCRYPT_EMAIL' not in uat
    assert 'EDGE_LETSENCRYPT_EMAIL_BOOTSTRAP: ${{ vars.KAORI_LETSENCRYPT_EMAIL }}' in edge
    assert ': "${EDGE_LETSENCRYPT_EMAIL_BOOTSTRAP:?Missing KAORI_LETSENCRYPT_EMAIL bootstrap variable}"' in edge
    assert 'export EDGE_LETSENCRYPT_EMAIL_BOOTSTRAP="$letsencrypt_email"' in edge


def test_shared_edge_runbook_documents_independent_multi_application_ingress() -> None:
    readme = EDGE_README.read_text(encoding='utf-8')

    required = (
        'Shared Server Edge Gateway',
        'edge-public',
        '/opt/shared-edge',
        'kaori-web',
        'n8n',
        'prepare.sh',
        'apply.sh',
        'cutover-complete',
        'unknown Host/SNI',
        'Certbot',
        'Docker socket',
    )
    for marker in required:
        assert marker in readme

    assert 'KAORI application redeploy must not interrupt other registered applications' in readme
