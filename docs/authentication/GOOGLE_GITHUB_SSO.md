# Google and GitHub SSO

## Boundary

KAORI implements two explicit browser SSO adapters:

- Google through OpenID Connect authorization-code flow.
- GitHub through OAuth App authorization-code flow.

They share the external identity projection table but do not share protocol assumptions or admission policy.

The complete administrator configuration procedure is maintained in:

```text
docs/authentication/IDENTITY_PROVIDER_CONFIGURATION.md
```

## Google identity contract

- Provider key: `google`
- Adapter key: `google_oidc`
- Stable subject: validated ID-token `sub`
- Requested scope: `openid email profile`
- Validation: state, nonce, ID-token signature, audience, issuer, and expiry
- Controlled JIT admission: verified email plus configured domain allow-list

Email is profile data and an admission signal. It is not the stable identity key.

## GitHub identity contract

- Provider key: `github`
- Adapter key: `github_oauth2`
- Stable subject: immutable numeric GitHub user ID
- Requested scope: `read:user user:email`
- Validation: state, authorization-code exchange, authenticated `/user` response
- Controlled JIT admission: configured GitHub login or numeric-ID allow-list

The GitHub login name can change and is not used as the stable identity key.

## Callback routes

Each provider uses its database key in the callback URL:

```text
/auth/sso/<provider-key>/callback
```

Examples:

```text
https://kaori.example.com/auth/sso/google-workspace/callback
https://kaori.example.com/auth/sso/github-corporate/callback
```

The external provider callback must match the generated KAORI callback used by the application.

## Secret boundary

The database stores only environment-variable names, for example:

```text
KAORI_GOOGLE_CLIENT_SECRET
KAORI_GITHUB_CLIENT_SECRET
```

Authorization codes, access tokens, ID tokens, and raw OAuth responses are never persisted.

## Controlled JIT

SSO JIT is disabled by default. Enabling it requires:

1. an active non-admin default role;
2. a Google domain allow-list or GitHub user allow-list;
3. an enabled provider with available runtime credentials.

LDAP JIT remains disabled and uses administrative directory provisioning.

## Login sequence

```text
Login page
→ SSO start route
→ state and optional nonce stored in signed session
→ provider authorization
→ callback state validation
→ provider-specific token and identity validation
→ existing projection lookup
→ controlled JIT projection when enabled and admitted
→ KAORI lifecycle check
→ session establishment
→ RBAC authorization
```
