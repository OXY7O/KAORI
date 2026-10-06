from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-staging-host.yml'


def test_staging_deployment_uses_only_canonical_host_identifiers() -> None:
    source = WORKFLOW.read_text(encoding='utf-8')

    required = (
        'KAORI_HOST: ${{ vars.KAORI_HOST }}',
        'KAORI_HOST_USER: ${{ vars.KAORI_HOST_USER }}',
        'KAORI_HOST_PORT: ${{ vars.KAORI_HOST_PORT }}',
        'KAORI_HOST_DEPLOY_ROOT: ${{ vars.KAORI_HOST_DEPLOY_ROOT }}',
        'KAORI_HOST_SSH_PRIVATE_KEY: ${{ secrets.KAORI_HOST_SSH_PRIVATE_KEY }}',
        'KAORI_HOST_SSH_PASSPHRASE: ${{ secrets.KAORI_HOST_SSH_PASSPHRASE }}',
        'KAORI_HOST_KNOWN_HOSTS: ${{ secrets.KAORI_HOST_KNOWN_HOSTS }}',
    )
    for marker in required:
        assert marker in source

    for marker in (
        '${KAORI_HOST:?Missing KAORI_HOST variable}',
        '${KAORI_HOST_USER:?Missing KAORI_HOST_USER variable}',
        '${KAORI_HOST_SSH_PRIVATE_KEY:?Missing KAORI_HOST_SSH_PRIVATE_KEY secret}',
        '${KAORI_HOST_SSH_PASSPHRASE:?Missing KAORI_HOST_SSH_PASSPHRASE secret}',
        '${KAORI_HOST_KNOWN_HOSTS:?Missing KAORI_HOST_KNOWN_HOSTS secret}',
        'target="$KAORI_HOST_USER@$KAORI_HOST"',
        'port="${KAORI_HOST_PORT:-22}"',
        'deploy_root="${KAORI_HOST_DEPLOY_ROOT:-/opt/kaori}"',
    ):
        assert marker in source


def test_legacy_vps_identifiers_are_removed_after_canonical_cutover() -> None:
    source = WORKFLOW.read_text(encoding='utf-8')

    assert 'KAORI_VPS_' not in source
