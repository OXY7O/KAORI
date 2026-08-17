from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_super_admin_is_local_database_break_glass_authority_end_to_end() -> None:
    model = read('app/models/user.py')
    service = read('app/users/service.py')
    directory = read('app/users/directory.py')
    form = read('app/templates/users/form.html')

    assert "if self.is_super_admin and self.auth_source == 'database':" in model
    assert "return 'unassigned'" in model
    assert 'def active_local_super_admin_count()' in service
    assert 'def is_last_active_local_super_admin(user: User)' in service
    assert "User.auth_source == 'database'" in service
    assert 'Super Admin authority is reserved for Local Database break-glass accounts.' in service
    assert "target.is_super_admin and target.auth_source != 'database'" in service
    assert "user.auth_source == 'database'" in directory
    assert "'label': 'Break-glass'" in directory
    assert 'Local Database break-glass authority' in form
    assert 'provider-independent' not in form


def test_user_directory_projects_effective_access_instead_of_lifecycle_only() -> None:
    directory = read('app/users/directory.py')
    table = read('app/templates/users/partials/_table.html')
    detail = read('app/templates/users/partials/_user_detail.html')
    summary = read('app/templates/users/partials/_summary_cards.html')

    for token in (
        "'label': 'Unassigned'",
        "'label': 'Blocked'",
        "'label': 'Allowed'",
        "identity_context['identity_state'] != 'Ready'",
        "'reason': 'The assigned RBAC role is inactive.'",
    ):
        assert token in directory
    assert 'user_view.access.label' in table
    assert 'user_view.access.reason' in detail
    assert 'identity_context.identity_state' in detail
    assert 'Access Findings' in summary
    assert 'Local Super Admins' in summary


def test_user_access_summary_detects_rbac_identity_and_invalid_break_glass_findings() -> None:
    summary = read('app/users/access_summary.py')
    overview = read('app/access/overview/presentation.py')

    assert "User.auth_source == 'database'" in summary
    assert "'unassigned_active_users': unassigned_active_users" in summary
    assert "'inactive_role_users': inactive_role_users" in summary
    assert "'external_identity_review': external_identity_review" in summary
    assert "'invalid_external_super_admins': invalid_external_super_admins" in summary
    assert "'access_review': access_review" in summary
    assert "summary['access_review']" in overview
    assert 'active Local Database' in overview


def test_ldap_administrative_projection_requires_short_lived_signed_directory_evidence() -> None:
    proof = read('app/identity_providers/provisioning_proof.py')
    routes = read('app/identity_providers/routes.py')
    forms = read('app/identity_providers/forms.py')
    template = read('app/templates/access/identity_providers/directory_provisioning.html')

    assert 'URLSafeTimedSerializer' in proof
    assert 'PROJECTION_PROOF_MAX_AGE_SECONDS = 600' in proof
    assert "'provider_id': int(provider_id)" in proof
    assert "'user_id': int(user_id)" in proof
    assert 'verify_projection_proof(' in routes
    assert 'issue_projection_proof(' in routes
    assert 'projection_proof = HiddenField(validators=[DataRequired()])' in forms
    assert 'name="projection_proof"' in template
    for forbidden in (
        'name="subject"',
        'name="external_username"',
        'name="distinguished_name"',
        'name="display_name"',
    ):
        assert forbidden not in template


def test_user_directory_is_split_from_mutation_service_without_expanding_code_health_debt() -> None:
    service = read('app/users/service.py')
    directory = read('app/users/directory.py')
    routes = read('app/users/routes.py')
    baseline = read('docs/architecture/code-health-debt-baseline.json')

    assert 'def build_users_payload(' not in service
    assert 'def build_users_payload(' in directory
    assert 'def build_user_identity_context(' in directory
    assert 'from app.users.directory import (' in routes
    assert '"app/users/service.py":' not in baseline


def test_local_user_email_uses_canonical_email_validation() -> None:
    forms = read('app/users/forms.py')
    assert 'Email()' in forms
    assert "email = StringField('Email', validators=[DataRequired(), Email(), Length(max=255)])" in forms


def test_break_glass_authority_is_enforced_at_database_boundary() -> None:
    model = read('app/models/user.py')
    migration = read('migrations/versions/20260817_user_super_admin_break_glass.py')

    assert "NOT is_super_admin OR auth_source = 'database'" in model
    assert "name='ck_users_super_admin_local_database'" in model
    assert 'UPDATE users SET is_super_admin = false' in migration
    assert "auth_source <> 'database'" in migration
    assert 'op.create_check_constraint(' in migration
    assert "'ck_users_super_admin_local_database'" in migration
