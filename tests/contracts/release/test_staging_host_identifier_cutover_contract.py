from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / '.github' / 'workflows' / 'deploy-staging-host.yml'


def test_staging_deployment_exposes_canonical_host_identifiers_with_legacy_fallback() -> None:
    source = WORKFLOW.read_text(encoding='utf-8')

    required = (
        'KAORI_HOST: ${{ vars.KAORI_HOST || vars.KAORI_VPS_HOST }}',
        'KAORI_HOST_USER: ${{ vars.KAORI_HOST_USER || vars.KAORI_VPS_USER }}',
        'KAORI_HOST_PORT: ${{ vars.KAORI_HOST_PORT || vars.KAORI_VPS_PORT }}',
        'KAORI_HOST_DEPLOY_ROOT: ${{ vars.KAORI_HOST_DEPLOY_ROOT || vars.KAORI_VPS_DEPLOY_ROOT }}',
        'KAORI_HOST_SSH_PRIVATE_KEY: ${{ secrets.KAORI_HOST_SSH_PRIVATE_KEY || secrets.KAORI_VPS_SSH_PRIVATE_KEY }}',
        'KAORI_HOST_SSH_PASSPHRASE: ${{ secrets.KAORI_HOST_SSH_PASSPHRASE || secrets.KAORI_VPS_SSH_PASSPHRASE }}',
        'KAORI_HOST_KNOWN_HOSTS: ${{ secrets.KAORI_HOST_KNOWN_HOSTS || secrets.KAORI_VPS_KNOWN_HOSTS }}',
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


def test_legacy_vps_identifiers_are_only_compatibility_inputs() -> None:
    source = WORKFLOW.read_text(encoding='utf-8')

    legacy_runtime_markers = (
        '${KAORI_VPS_HOST:?',
        '${KAORI_VPS_USER:?',
        '${KAORI_VPS_PORT:-',
        '${KAORI_VPS_DEPLOY_ROOT:-',
        '$KAORI_VPS_USER@$KAORI_VPS_HOST',
        '$KAORI_VPS_SSH_PRIVATE_KEY',
        '$KAORI_VPS_SSH_PASSPHRASE',
        '$KAORI_VPS_KNOWN_HOSTS',
    )
    for marker in legacy_runtime_markers:
        assert marker not in source
