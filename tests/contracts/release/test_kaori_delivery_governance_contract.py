from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / 'docs/engineering/KAORI_DELIVERY_WORKFLOW.md'
PROJECT_SETUP = ROOT / 'docs/engineering/KAORI_GITHUB_PROJECT_SETUP.md'
LABEL_CATALOG = ROOT / 'docs/engineering/KAORI_GITHUB_LABEL_CATALOG.md'
ISSUE_DIR = ROOT / '.github/ISSUE_TEMPLATE'
QUALITY_WORKFLOW = ROOT / '.github/workflows/quality.yml'
DEVELOPER_WORKFLOW = ROOT / '.github/workflows/developer-check.yml'
PR_TEMPLATE = ROOT / '.github/PULL_REQUEST_TEMPLATE.md'
CI_CD_DOC = ROOT / 'docs/setup/GITHUB_ACTIONS_CI_CD.md'
RECOVERY_DOC = ROOT / 'docs/deployment/CI_CD_RECOVERY_CONTRACT.md'
CDEVENTS_ARCHITECTURE = ROOT / 'docs/architecture/cdevents-delivery-lineage.md'
ARCHITECTURE_INDEX = ROOT / 'docs/architecture/README.md'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def load_form(name: str) -> dict:
    return yaml.safe_load((ISSUE_DIR / name).read_text(encoding='utf-8'))


def test_delivery_workflow_locks_current_lifecycle_branch_and_uat_authority() -> None:
    source = read(WORKFLOW)
    for token in (
        '**Governance Version:** 2.1',
        'Inbox',
        'Backlog',
        'Ready',
        'In Progress',
        'Review',
        'UAT',
        'Done',
        'Only two branches are long-lived by default',
        'main',
        'kaori/staging',
        'kaori/working',
        'Developer Check',
        'Pre-Ready',
        'Full Admission',
        'exact evidence reuse',
        'authority fingerprint',
        'FALLBACK',
        'Local UAT',
        'merge commit',
    ):
        assert token in source


def test_delivery_governance_locks_artifact_backed_vps_release_path() -> None:
    workflow = read(WORKFLOW)
    project = read(PROJECT_SETUP)
    template = read(PR_TEMPLATE)

    for token in (
        'immutable OCI image',
        'OCI digest',
        'VPS UAT',
        'https://kaori.cloud',
        'Semantic Versioning',
        'without rebuilding',
    ):
        assert token in workflow

    for token in (
        'OCI digest',
        'VPS UAT',
        'Semantic Versioning',
        'production RUN',
    ):
        assert token in project

    assert 'Project Metadata' in workflow
    assert 'must not' in workflow
    assert 'Artifact / Release Evidence' in template
    assert 'UAT-approved OCI digest' in template


def test_issue_forms_use_native_issue_type_without_title_prefixes() -> None:
    expected = {
        'epic.yml': 'Epic',
        'user-story.yml': 'User Story',
        'bug.yml': 'Bug',
        'task.yml': 'Task',
        'spike.yml': 'Spike',
        'chore.yml': 'Chore',
        'technical-debt.yml': 'Technical Debt',
    }
    for filename, name in expected.items():
        form = load_form(filename)
        assert form['name'] == name
        assert form['title'] == ''
        assert form['body']
        markdown = '\n'.join(
            item.get('attributes', {}).get('value', '') for item in form['body'] if item.get('type') == 'markdown'
        )
        assert 'Native GitHub Issue Type' in markdown


def test_blank_issue_creation_is_disabled() -> None:
    config = load_form('config.yml')
    assert config['blank_issues_enabled'] is False


def test_pull_request_template_requires_governed_delivery_evidence() -> None:
    source = read(PR_TEMPLATE)
    for token in (
        'Linked Work',
        'Why',
        'What Changed',
        'Out of Scope',
        'Acceptance Criteria Coverage',
        'Verification Evidence',
        'Security Impact',
        'Migration / Data Impact',
        'Observability / Operational Impact',
        'UAT',
        'Release Impact',
    ):
        assert token in source
    assert 'Refs #<issue>' in source
    assert 'Closes #<issue>' in source


def test_project_setup_locks_current_fields_views_and_authorities() -> None:
    source = read(PROJECT_SETUP)
    for token in (
        'Native GitHub Issue Type',
        'Inbox',
        'Backlog',
        'Ready',
        'In Progress',
        'Review',
        'UAT',
        'Done',
        'Urgent',
        'High',
        'Medium',
        'Low',
        '1, 2, 3, 5, 8',
        '00 - Work Register',
        '01 - Inbox',
        '02 - Backlog & Ready',
        '03 - Current Sprint',
        '04 - Delivery Flow',
        '05 - Stabilization',
        '06 - UAT & Release',
        '07 - Bugs & Debt',
        '08 - Roadmap',
        'PR cards',
        'Local UAT',
    ):
        assert token in source
    assert 'P0 — Critical' not in source
    assert 'P2 — Normal' not in source


def test_label_catalog_preserves_documentation_and_avoids_native_metadata_duplication() -> None:
    source = read(LABEL_CATALOG)
    for token in (
        'documentation',
        'area:platform',
        'area:reports',
        'scope:frontend',
        'scope:backend',
        'scope:ci',
        'quality:security',
        'quality:reliability',
        'impact:migration',
        'workflow:blocked',
        'workflow:expedite',
    ):
        assert token in source
    for forbidden in (
        'scope:documentation',
        'type:bug',
        'type:task',
        'priority:high',
        'status:done',
        'status:in-progress',
    ):
        assert forbidden not in source


def test_github_metadata_hygiene_and_recovery_contract_is_documented() -> None:
    workflow = read(WORKFLOW)
    project = read(PROJECT_SETUP)
    catalog = read(LABEL_CATALOG)

    for token in (
        'Read-first recovery order',
        'Repository Metadata Hygiene Gate',
        'repo:OXY7O/KAORI is:pr no:label',
        'repo:OXY7O/KAORI is:pr no:assignee',
        'Never use Full Admission as the development/debug loop',
    ):
        assert token in workflow

    for token in (
        'Metadata Synchronization Gate',
        'Every governed Issue and PR must be added to the KAORI Project',
        'Project fields cannot be mutated by connected tooling',
    ):
        assert token in project

    for token in (
        'Label Admission Gate',
        'An uncataloged label must not be used',
        'name, color, and description',
    ):
        assert token in catalog


def test_progressive_ci_routes_only_governed_integration_pushes_and_staging_prs() -> None:
    source = read(QUALITY_WORKFLOW)
    assert '- kaori/staging' in source
    assert '- main' in source
    assert '- "release/**"' in source
    assert '- "kaori/**"' not in source
    assert '- kaori/working' not in source
    assert 'validation-profile:' in source
    assert 'integration-smoke:' in source
    assert "needs.validation-profile.outputs.execution == 'full'" in source
    assert "needs.validation-profile.outputs.execution == 'fast'" in source
    assert 'KAORI_PROFILE_VERSION: "3"' in source
    assert 'name: CI Admission' in source


def test_work_branches_use_targeted_checks_before_ready_admission() -> None:
    quality = read(QUALITY_WORKFLOW)
    developer = read(DEVELOPER_WORKFLOW)
    workflow = read(WORKFLOW)

    pull_request_block = quality.split('pull_request:', 1)[1].split('permissions:', 1)[0]
    assert '- kaori/staging' not in pull_request_block
    assert '- main' in pull_request_block

    assert 'branches:\n      - kaori/staging' in developer
    assert "startsWith(github.event.pull_request.head.ref, 'kaori/')" in developer
    assert "github.event.pull_request.head.ref != 'kaori/staging'" in developer
    assert "needs.developer-check.result == 'success'" in developer
    assert 'github.event.pull_request.draft == false' in developer
    assert 'uses: ./.github/workflows/quality.yml' in developer

    assert 'Every `kaori/*` branch except `kaori/staging` is a work branch.' in workflow
    assert (
        'Work branches use path-aware Developer Check / targeted validation while Draft and on the exact Ready head.'
        in workflow
    )
    assert 'Comprehensive validation authority begins at the Ready/frozen-candidate boundary' in workflow


def test_draft_developer_check_is_path_aware_and_non_authoritative() -> None:
    source = read(DEVELOPER_WORKFLOW)

    assert 'name: Developer Check' in source
    assert 'name: Route Checks' in source
    assert 'name: Developer Check' in source
    assert 'wide=true' in source
    assert 'scripts/quality_gate.sh --static' not in source
    assert 'run-runtime-validation.sh' not in source


def test_canonical_ci_cd_document_matches_current_staged_delivery_model() -> None:
    source = read(CI_CD_DOC)

    for token in (
        'issue branch',
        'Developer Check',
        'kaori/staging',
        'Full Admission',
        'immutable RC',
        'UAT',
        'human acceptance',
        'stable promotion',
        'same immutable digest',
        'roll-forward',
        'rollback',
        'Semgrep 1.177.0',
        'CI_CD_RECOVERY_CONTRACT.md',
    ):
        assert token in source

    for obsolete in (
        'kaori/working',
        'Production CD     : not implemented yet',
        'Application deployment is intentionally outside the current scope',
        'Semgrep      1.174.0',
        '# FUTURE CD',
    ):
        assert obsolete not in source


def test_ci_cd_recovery_contract_keeps_cdevents_observability_non_authoritative() -> None:
    source = read(RECOVERY_DOC)

    for token in (
        'Continuous Integration',
        'Continuous Delivery',
        'Continuous Deployment',
        'failed deployment',
        'rollback',
        'roll-forward',
        'fresh Full Admission',
        '#440',
        'observability',
        'authorization',
    ):
        assert token.lower() in source.lower()

    assert 'do not become an authorization plane' in source.lower()


def test_cdevents_architecture_pins_spec_binding_and_vocabulary_versions() -> None:
    source = read(CDEVENTS_ARCHITECTURE)
    architecture_index = read(ARCHITECTURE_INDEX)

    for token in (
        'CDEvents v0.5.0',
        'context.specversion',
        '0.5.0',
        'CloudEvents specversion',
        '1.0',
        'dev.cdevents.change.created.0.4.0',
        'dev.cdevents.change.updated.0.3.0',
        'dev.cdevents.change.reviewed.0.3.0',
        'dev.cdevents.change.merged.0.3.0',
        'dev.cdevents.pipelinerun.started.0.3.0',
        'dev.cdevents.pipelinerun.finished.0.3.0',
        'dev.cdevents.build.started.0.3.0',
        'dev.cdevents.build.finished.0.3.0',
        'dev.cdevents.artifact.packaged.0.3.0',
        'dev.cdevents.artifact.published.0.3.0',
        'dev.cdevents.artifact.signed.0.3.0',
        'dev.cdevents.service.deployed.0.3.0',
        'dev.cdevents.service.upgraded.0.3.0',
        'dev.cdevents.service.rolledback.0.3.0',
    ):
        assert token in source

    assert 'cdevents-delivery-lineage.md' in architecture_index


def test_cdevents_architecture_defines_canonical_delivery_identity_and_retry_semantics() -> None:
    source = read(CDEVENTS_ARCHITECTURE)

    for token in (
        'Repository identity',
        'Change identity',
        'Source SHA',
        'Workflow run identity',
        'Event ID',
        'chainId',
        'UUID',
        'RC identity',
        'OCI PURL',
        'UAT environment',
        'Stable release identity',
        'retry',
        'retransmission',
        'deduplication',
        'idempotency',
    ):
        assert token.lower() in source.lower()

    assert 'commit SHA is not a chain ID' in source
    assert 'mutable tag is never artifact authority' in source


def test_cdevents_architecture_locks_security_trust_and_failure_boundaries() -> None:
    source = read(CDEVENTS_ARCHITECTURE)

    for token in (
        'Producer trust',
        'Sensitive-data exclusion',
        'github.token',
        'secrets',
        'SSH private key',
        'kubeconfig',
        'database URL',
        'fail closed',
        'non-authoritative consumer',
        'customData',
        'version upgrade',
    ):
        assert token.lower() in source.lower()

    assert 'CDEvents cannot authorize' in source
    assert 'no broker' in source.lower()
