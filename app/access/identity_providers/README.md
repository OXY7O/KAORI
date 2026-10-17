# Identity Providers Application Workspace

`app/access/identity_providers` owns the authenticated administrative workspace for external identity providers. It does not implement authentication protocols and it does not own user lifecycle mutations.

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

Provider-specific protocol behavior must not be added here. It belongs under `app/access/authentication/identity_provider/providers/<provider>/` or `app/access/authentication/identity_provider/adapters/<adapter>/`.

## Firefox laptop contextual guidance UAT (#2279)

Google OIDC Guidance and Exact Callback URL help use concise copy while the
underlying setup steps and exact generated scheme/host/path/provider-key callback
remain unchanged. The existing Provider/Adapter Boundary text already expresses
a compact one-line statement and is retained. Related Add User provider navigation
copy is covered by bounded User Management issue #2278.

The dynamic registered-account / local break-glass count shown in the operator
screenshot has not been mapped to its committed source owner; it is **not**
silently rewritten or considered fixed. Capture the exact page and source
projection during Dev Container Firefox UAT. Desktop one-line appearance,
responsive/mobile wrapping, keyboard, light/dark and human acceptance remain
PENDING until browser execution; no official admission is implied.
