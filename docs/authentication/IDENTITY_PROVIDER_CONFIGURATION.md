# Identity Provider Configuration Runbook

## Purpose

This runbook is the canonical administrator guide for configuring the external identity providers currently implemented by KAORI:

- LDAP / Active Directory
- Google OpenID Connect
- GitHub OAuth

Local Database authentication remains enabled as the independent break-glass recovery path. External providers verify identity; KAORI remains authoritative for local account lifecycle and RBAC authorization.

## Shared KAORI workflow

Use the same activation sequence for every provider:

1. Create the provider while **Enabled** is off.
2. Complete only the fields displayed for the selected provider type.
3. Provide the referenced secret environment variable to every KAORI web application instance.
4. Save the provider.
5. Run **Validate** from **Identity Providers**.
6. Resolve connection, callback, secret, or admission-policy errors.
7. Enable the provider.
8. Test with a non-administrative identity.
9. Confirm login/logout events appear in **Activity Audit Log**.

Provider records store secret **environment-variable names**, never secret values.

## Shared fields

| KAORI field   | Purpose                                                                  | Example                                             |
| ------------- | ------------------------------------------------------------------------ | --------------------------------------------------- |
| Provider Key  | Stable URL-safe key. For SSO it becomes part of the callback URL.        | `corp-ldap`, `google-workspace`, `github-corporate` |
| Display Name  | Administrator and user-facing provider name.                             | `Corporate Active Directory`                        |
| Provider Type | Selects the provider-specific configuration and runtime adapter.         | `LDAP / Active Directory`                           |
| Enabled       | Allows authentication only after configuration and validation are ready. | Off during initial setup                            |

---

# LDAP / Active Directory

## KAORI authentication model

LDAP uses administrative provisioning:

1. KAORI binds with a read-only service account.
2. An administrator searches the directory from **LDAP Directory Provisioning**.
3. The administrator selects the identity, assigns a KAORI role, and creates the local projection.
4. The user signs in through the normal username/password form.
5. KAORI resolves the provisioned identity link and performs a bind using the user's distinguished name and submitted password.

KAORI does not store the LDAP user's password.

## Network and TLS prerequisites

- Allow KAORI to reach the LDAP server.
- Use TCP 636 for LDAPS or TCP 389 for StartTLS.
- Install the issuing CA certificate in the KAORI container trust store when the LDAP certificate is private or internally issued.
- The certificate hostname must match the hostname configured in **LDAP Server URI**.
- Plain LDAP is intended only for isolated development testing.

KAORI validates server certificates for LDAPS and StartTLS. StartTLS is negotiated before the bind credentials are sent.

## Service account requirements

Create a dedicated read-only directory account. It needs only:

- bind permission;
- subtree search permission under the configured Base DN;
- read access to the configured username, email, display-name, and stable-ID attributes.

It does not need account creation, password reset, group modification, or directory write permissions.

## LDAP fields

| KAORI field                        | Required value                                            | Active Directory example                             | Generic LDAP example                         |
| ---------------------------------- | --------------------------------------------------------- | ---------------------------------------------------- | -------------------------------------------- |
| LDAP Server URI                    | LDAP endpoint and optional port                           | `ldaps://dc01.example.com:636`                       | `ldaps://ldap.example.com:636`               |
| TLS Mode                           | `LDAPS`, `StartTLS`, or development-only plain            | `LDAPS`                                              | `StartTLS`                                   |
| Base DN                            | Root of the searchable user subtree                       | `OU=Users,DC=example,DC=com`                         | `ou=people,dc=example,dc=com`                |
| Bind DN                            | Read-only service account identity                        | `CN=svc-kaori,OU=Service Accounts,DC=example,DC=com` | `uid=svc-kaori,ou=service,dc=example,dc=com` |
| Bind Password Environment Variable | Environment-variable name containing the service password | `KAORI_LDAP_BIND_PASSWORD`                           | `KAORI_LDAP_BIND_PASSWORD`                   |
| User Search Filter                 | LDAP filter containing `{query}`                          | See examples below                                   | See examples below                           |
| Username Attribute                 | Login name copied into KAORI                              | `sAMAccountName` or `userPrincipalName`              | `uid`                                        |
| Email Attribute                    | Primary email                                             | `mail`                                               | `mail`                                       |
| Display Name Attribute             | Human-readable name                                       | `displayName`                                        | `cn`                                         |
| Stable ID Attribute                | Immutable identity subject                                | `objectGUID`                                         | `entryUUID`                                  |

For Active Directory, `objectGUID` is preferred over distinguished name because the GUID survives object rename and move operations.

## Search filter examples

### Active Directory users

```ldap
(&(objectCategory=person)(objectClass=user)(|(sAMAccountName=*{query}*)(userPrincipalName=*{query}*)(mail=*{query}*)(displayName=*{query}*)))
```

### Generic LDAP inetOrgPerson

```ldap
(&(objectClass=inetOrgPerson)(|(uid=*{query}*)(mail=*{query}*)(cn=*{query}*)))
```

KAORI escapes the administrator's search value before replacing `{query}`. Keep the filter template syntactically valid and restrict it to user objects where possible.

## Runtime secret

In development `.env`:

```dotenv
KAORI_LDAP_BIND_PASSWORD=replace-with-directory-service-password
```

In Docker Compose, make the variable available to the web application container. Production deployments should source it from the deployment secret mechanism rather than committing it to the repository.

The value entered in the KAORI provider form is only:

```text
KAORI_LDAP_BIND_PASSWORD
```

## Validation and provisioning

1. Save the LDAP provider while disabled.
2. Ensure the bind secret is present in the running KAORI container.
3. Run **Validate**. This opens the configured connection, negotiates TLS when selected, and performs the service bind.
4. Enable the provider.
5. Open **LDAP Directory Provisioning**.
6. Search by username, email, or display name.
7. Select the identity, choose a non-administrative or explicitly approved role, and provision the user.
8. Test the standard KAORI login form with the LDAP username and password.

## LDAP troubleshooting

| Symptom                                    | Check                                                                                                                                                  |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Provider validation reports missing secret | Confirm the exact environment-variable name and restart the KAORI container after adding it.                                                           |
| TLS validation fails                       | Confirm container CA trust, certificate chain, certificate hostname, port, and selected TLS mode.                                                      |
| Service bind fails                         | Confirm Bind DN syntax, password, account state, and directory authentication policy.                                                                  |
| Search returns no users                    | Confirm Base DN, search filter, mapped attributes, and service-account read permissions.                                                               |
| Provisioned user cannot sign in            | Confirm the stored distinguished name is current, provider remains enabled, KAORI user is active, and the directory account is not locked or disabled. |

---

# Google OpenID Connect

## Google application prerequisites

Create or select a Google Cloud project and configure the Google OAuth consent/branding settings required for the intended audience. Create an OAuth 2.0 client of type **Web application**.

KAORI uses server-side authorization-code flow and requests:

```text
openid email profile
```

The Google redirect URI must exactly match the callback generated from the KAORI external URL and Provider Key.

## Google fields

| KAORI field                        | Required value                                                | Example                                     |
| ---------------------------------- | ------------------------------------------------------------- | ------------------------------------------- |
| Provider Key                       | Stable callback segment                                       | `google-workspace`                          |
| Display Name                       | Login-button label                                            | `Google Workspace`                          |
| Google Client ID                   | OAuth client ID from Google                                   | `1234567890-abc.apps.googleusercontent.com` |
| Client Secret Environment Variable | Runtime variable containing the Google client secret          | `KAORI_GOOGLE_CLIENT_SECRET`                |
| Enable controlled JIT provisioning | Optional automatic KAORI user creation after admission checks | Off by default                              |
| JIT Default Role                   | Active non-admin KAORI role                                   | `viewer` or an approved custom role         |
| Allowed Google Domains             | Verified email domains admitted for JIT                       | `example.com`                               |

## Google callback

Format:

```text
https://<kaori-host>/auth/sso/<provider-key>/callback
```

Example:

```text
https://kaori.example.com/auth/sso/google-workspace/callback
```

Register this exact value as an authorized redirect URI for the Google Web application client. Scheme, host, case, path, and trailing slash behavior must match.

## Google runtime secret

```dotenv
KAORI_GOOGLE_CLIENT_SECRET=replace-with-google-client-secret
```

Enter only this variable name in KAORI:

```text
KAORI_GOOGLE_CLIENT_SECRET
```

## Google admission behavior

Without JIT:

- Google verifies the identity.
- KAORI permits access only when an existing `ExternalIdentityLink` already maps the Google `sub` claim to a KAORI user.

With controlled JIT:

- Google must return a verified email.
- The email domain must match **Allowed Google Domains**.
- KAORI creates a local user projection with the selected non-admin default role.
- The stable external subject is the Google `sub` claim, not the email address.

## Google activation steps

1. Create the Web application OAuth client in Google.
2. Copy the KAORI callback into the authorized redirect URI list.
3. Copy the Client ID into KAORI.
4. Place the Client Secret in the KAORI runtime environment.
5. Configure JIT and allowed domains only when automatic account creation is intended.
6. Save while disabled.
7. Run **Validate**.
8. Enable the provider.
9. Confirm the Google button appears on the login page.
10. Test sign-in and verify the authentication event in Activity Audit Log.

## Google troubleshooting

| Symptom                                            | Check                                                                                                                                  |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Google button is absent                            | Provider must be enabled, Client ID configured, secret variable name configured, and the secret variable present in the KAORI runtime. |
| `redirect_uri_mismatch`                            | Compare the Google authorized redirect URI with the exact callback displayed in KAORI.                                                 |
| Sign-in succeeds at Google but KAORI denies access | Confirm the identity is pre-provisioned or JIT is enabled with a valid role and allowed domain.                                        |
| JIT domain denied                                  | Confirm Google returned a verified email and the domain is listed without `@`.                                                         |

---

# GitHub OAuth

## GitHub application prerequisites

Create a GitHub OAuth App under an account or organization that administrators control:

1. Open GitHub **Settings**.
2. Open **Developer settings**.
3. Open **OAuth Apps**.
4. Create a new OAuth App.
5. Set the application name and homepage URL.
6. Set the **Authorization callback URL** to the exact KAORI callback.
7. Register the application and generate a client secret.

A GitHub OAuth App supports one callback URL, so use separate OAuth Apps when development, UAT, and production require different callbacks.

KAORI requests:

```text
read:user user:email
```

The numeric GitHub user ID is stored as the stable subject. The login name is profile data and may change.

## GitHub fields

| KAORI field                        | Required value                                       | Example                             |
| ---------------------------------- | ---------------------------------------------------- | ----------------------------------- |
| Provider Key                       | Stable callback segment                              | `github-corporate`                  |
| Display Name                       | Login-button label                                   | `GitHub`                            |
| GitHub Client ID                   | OAuth App client ID                                  | Provider-generated value            |
| Client Secret Environment Variable | Runtime variable containing the GitHub client secret | `KAORI_GITHUB_CLIENT_SECRET`        |
| Enable controlled JIT provisioning | Optional automatic account creation                  | Off by default                      |
| JIT Default Role                   | Active non-admin KAORI role                          | `viewer` or an approved custom role |
| Allowed GitHub Users               | Numeric GitHub IDs or login names                    | `583231`                            |

## GitHub callback

Format:

```text
https://<kaori-host>/auth/sso/<provider-key>/callback
```

Example:

```text
https://kaori.example.com/auth/sso/github-corporate/callback
```

Set this as the GitHub OAuth App **Authorization callback URL**.

## GitHub runtime secret

```dotenv
KAORI_GITHUB_CLIENT_SECRET=replace-with-github-client-secret
```

Enter only this variable name in KAORI:

```text
KAORI_GITHUB_CLIENT_SECRET
```

## GitHub admission behavior

Without JIT:

- GitHub validates the OAuth flow and returns the authenticated profile.
- KAORI permits access only when an existing identity link maps the numeric GitHub user ID to a KAORI user.

With controlled JIT:

- The numeric GitHub user ID or current login must exist in **Allowed GitHub Users**.
- KAORI creates a local user projection with the selected non-admin default role.
- Prefer numeric IDs because login names can change.

## GitHub activation steps

1. Create the GitHub OAuth App.
2. Register the exact KAORI callback URL.
3. Copy the Client ID into KAORI.
4. Generate and store the Client Secret in the KAORI runtime environment.
5. Configure controlled JIT only when automatic creation is intended.
6. Save while disabled.
7. Run **Validate**.
8. Enable the provider.
9. Confirm the GitHub button appears on the login page.
10. Test sign-in and verify Activity Audit Log.

## GitHub troubleshooting

| Symptom                                 | Check                                                                                                       |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| GitHub button is absent                 | Provider must be enabled and its Client ID, secret variable name, and runtime secret must all be available. |
| Callback returns an authorization error | Confirm OAuth App ownership, Client ID/secret pair, and callback URL.                                       |
| Email is missing                        | KAORI requests `user:email`; confirm the user granted access and has an accessible verified email.          |
| JIT admission denied                    | Add the immutable numeric user ID or exact current login name to the allow-list.                            |

---

# Security boundaries

- Keep Local Database break-glass authentication available.
- Never store LDAP passwords, OAuth client secrets, authorization codes, access tokens, ID tokens, or provider response payloads in database fields or audit metadata.
- Give LDAP service accounts read-only permissions.
- Use TLS for LDAP and HTTPS for externally reachable SSO callbacks.
- Assign non-admin roles for JIT provisioning.
- Use explicit allow-lists for Google domains and GitHub users.
- Validate before enabling and test with a non-administrative identity.
- Review login failures and provider changes in Activity Audit Log.

# Implementation references

- Google OpenID Connect: https://developers.google.com/identity/openid-connect/openid-connect
- Google OAuth 2.0 Web Server Applications: https://developers.google.com/identity/protocols/oauth2/web-server
- GitHub Creating an OAuth App: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app
- GitHub Authorizing OAuth Apps: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps
- GitHub OAuth App Scopes: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps
- Microsoft Active Directory User Naming Attributes: https://learn.microsoft.com/en-us/windows/win32/ad/naming-properties
- Microsoft Active Directory Object Names and Identities: https://learn.microsoft.com/en-us/windows/win32/ad/object-names-and-identities
- ldap3 TLS documentation: https://ldap3.readthedocs.io/en/latest/ssltls.html
