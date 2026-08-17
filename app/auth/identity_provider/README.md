# Identity Provider Kernel

`app/auth/identity_provider` is the provider-neutral authentication kernel for external identity authorities.

```text
identity_provider/
├── catalog.py                 # source-controlled provider definitions
├── configuration.py           # canonical provider/adapter configuration projection
├── credential.py              # credential adapter contract
├── directory.py               # directory adapter + external identity contracts
├── browser.py                 # browser SSO contract
├── registry.py                # adapter registries
├── adapters/
│   └── ldap/                  # reusable LDAP transport/directory/credential adapter
└── providers/
    ├── google/                # Google-specific browser implementation
    └── github/                # GitHub-specific browser implementation
```

Core code depends on `provider_key`, `adapter_key`, provider family/flow, and adapter capabilities. Product names are valid only in provider definitions or provider-specific implementation packages. Adding a provider that reuses an existing adapter must not require schema, route, user-lifecycle, or core authentication refactoring.
