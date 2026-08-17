# Identity Providers Application Workspace

`app/identity_providers` owns the authenticated administrative workspace for external identity providers. It does not implement authentication protocols and it does not own user lifecycle mutations.

Canonical layering:

```text
Access / Authentication
  -> Identity Provider
      -> provider_key
      -> adapter_key
      -> admission policy / capabilities
      -> identity projection
```

Ownership:

- `routes.py`: administrative HTTP boundary and tab routing.
- `forms.py`: provider-neutral common form plus adapter-profile fields.
- `service.py`: registry/filter/pagination/presentation composition.
- `provisioning.py`: provider-neutral directory identity projection.
- `provisioning_proof.py`: short-lived signed identity evidence.
- `notifications.py`: operational feedback and Activity Audit integration.

Provider-specific protocol behavior must not be added here. It belongs under `app/auth/identity_provider/providers/<provider>/` or `app/auth/identity_provider/adapters/<adapter>/`.
