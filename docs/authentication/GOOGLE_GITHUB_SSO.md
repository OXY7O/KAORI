# Google and GitHub SSO

## Boundary

KAORI supports two explicit browser SSO adapters:

- Google through OpenID Connect authorization-code flow.
- GitHub through OAuth App authorization-code flow.

They share the external identity projection table but do not share protocol assumptions.

## Google identity contract

- Provider type: `google_oidc`
- Stable subject: verified ID-token `sub`
- Minimum scope: `openid email profile`
- Validation: state, nonce, token signature, audience, issuer, and expiry
- Admission policy for JIT: verified email plus configured domain allow-list

Email is profile data and an admission signal. It is not the stable identity key.

## GitHub identity contract

- Provider type: `github_oauth`
- Stable subject: immutable numeric GitHub user ID
- Minimum scope: `read:user user:email`
- Validation: state, authorization-code exchange, authenticated `/user` response
- Admission policy for JIT: configured GitHub login or numeric-ID allow-list

The GitHub login name can change and is not used as the stable identity key.

## Callback routes

Each provider uses its database key in the callback URL:

```text
/auth/sso/<provider-key>/callback
```

Examples:

```text
https://kaori.example.com/auth/sso/google/callback
https://kaori.example.com/auth/sso/github/callback
```

The registered callback in Google Cloud or GitHub must match the generated KAORI callback exactly.

## Secret boundary

The database stores only the environment-variable name:

```text
KAORI_GOOGLE_CLIENT_SECRET
KAORI_GITHUB_CLIENT_SECRET
```

Authorization codes, access tokens, ID tokens, and raw OAuth responses are never persisted.

## Controlled JIT

SSO JIT is disabled by default. Enabling it requires:

1. an active non-admin default role;
2. a Google domain allow-list or GitHub user allow-list;
3. an enabled and validated provider.

LDAP JIT remains disabled and continues to use administrative directory provisioning.

## Login sequence

```text
Login page
→ SSO start route
→ state and optional nonce stored in signed session
→ provider authorization
→ callback state validation
→ provider-specific token/identity validation
→ existing projection lookup
→ controlled JIT projection when enabled and admitted
→ KAORI lifecycle check
→ session establishment
→ RBAC authorization
```
