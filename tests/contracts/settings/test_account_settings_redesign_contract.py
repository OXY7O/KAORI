from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_account_hero_matches_general_context_pattern() -> None:
    hero = read("app/templates/settings/account/partials/_hero.html")
    assert "Account Posture" in hero
    assert "Authentication Evidence" in hero
    assert "Credential Posture" in hero
    assert "context_header" in hero
    assert "context_panel_metrics_classes" in hero
    assert hero.count("context_info") >= 3
    assert "Current Section Boundary" not in hero
    assert "context_single_action_classes" not in hero


def test_account_tabs_use_same_simple_navigation_contract_as_general() -> None:
    tabs = read("app/templates/settings/account/partials/_tabs.html")
    assert "border-b border-outline-default bg-surface-subtle px-5 pt-4" in tabs
    assert "flex gap-2 overflow-x-auto" in tabs
    assert "Account Profile & Access" in tabs
    assert "Recent Authentication Activity" in tabs
    assert "Credential Management" in tabs
    assert "activity_summary.total" not in tabs
    assert "identity_context.type_label" not in tabs
    assert "KAORI managed" not in tabs


def test_profile_workspace_uses_posture_grid_and_verified_signin_panel() -> None:
    profile = read("app/templates/settings/account/partials/_profile_cards.html")
    assert "Account Posture" in profile
    assert "Identity Source" in profile
    assert "Assigned Role" in profile
    assert "Account Lifecycle" in profile
    assert "Identity Profile" in profile
    assert "Last Verified Sign-In" in profile
    assert "table_label.status_indicator_label" in profile
    assert "Read-Only Account View" in profile


def test_profile_context_uses_expandable_boundaries_and_general_settings_link() -> None:
    context = read("app/templates/settings/account/partials/_profile_information.html")
    assert "data-account-profile-boundaries" in context
    assert context.count("rounded-2xl") >= 3
    assert "Current Identity Source" in context
    assert "Access Control Boundary" in context
    assert "Personal Presentation" in context
    assert "Open General Settings" in context
    assert "[&::-webkit-details-marker]:hidden" in context


def test_authentication_activity_keeps_summary_and_table_together() -> None:
    activity = read("app/templates/settings/account/partials/_recent_login_activity.html")
    assert "Successful Sign-Ins" in activity
    assert "Failed Sign-Ins" in activity
    assert "Sign-Out Events" in activity
    assert "table_ui.table_classes" in activity
    assert "table_label.status_indicator_label('Success', 'normal')" in activity
    assert "table_label.status_indicator_label('Failed', 'critical')" in activity
    assert "category='access', search=current_user.username" in activity


def test_activity_context_is_evidence_and_privacy_only() -> None:
    context = read("app/templates/settings/account/partials/_activity_information.html")
    assert "Recorded Evidence" in context
    assert "Result Interpretation" in context
    assert "Audit Privacy Boundary" in context
    assert "category='access', search=current_user.username" in context
    assert "event_type='authentication'" not in context
    assert "user_id=current_user.id" not in context
    assert "Passwords, LDAP bind secrets" in context


def test_credential_workspace_uses_security_posture_then_two_stage_form() -> None:
    credentials = read("app/templates/settings/account/partials/_change_password.html")
    assert "Credential Posture" in credentials
    assert "Credential Owner" in credentials
    assert "Password Policy" in credentials
    assert "Session Effect" in credentials
    assert "Replace Local Password" in credentials
    assert "Current Password" in credentials
    assert "New Password" in credentials
    assert "Confirm New Password" in credentials
    assert "Minimum 12 characters" in credentials
    assert "grid gap-4 md:grid-cols-2" in credentials
    assert "lg:grid-cols-3" not in credentials


def test_credential_context_uses_semantic_impact_states_and_single_boundary_panel() -> None:
    context = read("app/templates/settings/account/partials/_credential_information.html")
    assert "Credential Ownership" in context
    assert "Change Impact" in context
    assert "Credential Boundary" in context
    assert "status_indicator_label('Changed', 'maintenance')" in context
    assert "status_indicator_label('Preserved', 'normal')" in context
    assert "status_indicator_label('Revoked', 'warning')" in context
    assert "status_indicator_label('Recorded', 'info')" in context
    assert "Only Local Database password hashes are owned by KAORI" in context


def test_readme_locks_account_presentation_contract() -> None:
    readme = read("app/settings/README.md")
    assert "Account & Authentication presentation contract" in readme
    assert "compact posture summary" in readme
    assert "simple tab contract as General Settings" in readme
    assert "Last Verified Sign-In" in readme
    assert "Avoid hand-built status badges" in readme
