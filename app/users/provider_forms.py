from __future__ import annotations

from app.auth.provider_configuration import IdentityProviderConfiguration
from app.users.forms import IdentityProviderForm


def identity_provider_configuration_from_form(
    form: IdentityProviderForm,
) -> IdentityProviderConfiguration:
    """Project UI form fields into the provider-neutral Auth configuration DTO."""

    return IdentityProviderConfiguration(
        provider_type=str(form.provider_type.data or ''),
        key=str(form.key.data or ''),
        display_name=str(form.display_name.data or ''),
        enabled=bool(form.enabled.data),
        jit_enabled=bool(form.jit_enabled.data),
        server_uri=form.server_uri.data,
        base_dn=form.base_dn.data,
        bind_dn=form.bind_dn.data,
        bind_password_env=form.bind_password_env.data,
        user_filter=form.user_filter.data,
        tls_mode=str(form.tls_mode.data or 'ldaps'),
        username_attribute=str(form.username_attribute.data or ''),
        email_attribute=str(form.email_attribute.data or ''),
        display_name_attribute=str(form.display_name_attribute.data or ''),
        stable_id_attribute=str(form.stable_id_attribute.data or ''),
        oidc_client_id=form.oidc_client_id.data,
        oidc_client_secret_env=form.oidc_client_secret_env.data,
        default_role_id=form.default_role_id.data or None,
        allowed_domains=form.allowed_domains.data,
        allowed_subjects=form.allowed_subjects.data,
    )
