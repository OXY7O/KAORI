# Production internal DNS and provider CA trust — KAORI

Status: **implementation guidance and admission contract**, not executed change evidence.
Authority: deployment configuration in `docs/deployment/ENVIRONMENT_CONFIGURATION.md`,
`deploy/server/compose.server.yml`, `docs/authentication/IDENTITY_PROVIDER_CONFIGURATION.md`,
and bounded implementation issue #4786. Local lab override #4782 is **not** a production authority.

## Scope and responsibility

- **AD/DNS/PKI** own authoritative LDAP and Vault FQDN records, certificate
  issuance, trust anchors, renewal, name resolution and network controls.
- **KAORI** owns registered provider URLs, tightly scoped policy, runtime
  credentials in approved secret stores, TLS verification, validation
  evidence and identity/governance workflow.
- This repository's currently governed UAT/production runtime is
  **Docker Compose on a server**. Kubernetes examples below are illustrative
  for a future separately admitted adapter; no production Kubernetes
  resources or CoreDNS changes have been applied.
- Avoid static host overrides. Use authoritative private DNS or approved
  conditional forwarding first. Never insert manual lines into a live
  container/Pod `/etc/hosts` as an operating procedure.

## 1. Approve the production PKI material before delivery

1. Inventory the approved LDAP FQDN and DNS owner (for example
   `adds.kaori.cloud`), network route, certificate issuer, renewal owner,
   expiry window and allowed outbound TCP 636. For Vault, separately
   inventory its approved production HTTPS FQDN and outbound port.
2. Obtain **public CA certificates / necessary intermediate chain** through
   the official PKI distribution process. Do not copy `tls.key`, export
   private keys, or use `secrets/trust/` from the DevContainer as a production
   source of truth.
3. Inspect the issuer CA certificate:

   ```bash
   openssl x509 -in approved-ldap-issuing-ca.pem -noout -subject -issuer -dates
   openssl x509 -in approved-ldap-issuing-ca.pem -noout -ext basicConstraints -ext keyUsage
   ```

   A certificate used as a normal issuing CA needs `CA:TRUE` and, when
   Key Usage is present, `keyCertSign`. Verify the **server leaf**
   separately for SAN `DNS:adds.kaori.cloud`, appropriate server
   authentication, and a valid issuer chain. A `Verify return code: 0`
   using an explicitly trusted self-signed leaf is **not evidence** that
   the file is an issuing CA or that enterprise PKI has admitted it.
   A self-signed leaf direct-trust exception needs security approval,
   fingerprint evidence, restricted scope, explicit expiry and a
   rotation/rollback plan; do not silently classify it as a CA.
4. Certificate fingerprints can be recorded without exposing credentials:

   ```bash
   openssl x509 -in approved-ldap-issuing-ca.pem -noout -fingerprint -sha256
   ```

## 2. Governed Docker Compose production — existing KAORI adapter

The approved server stack uses two Compose authorities:

```text
compose.production.yml
deploy/server/compose.server.yml
```

The server config is split into:

```text
/etc/kaori/app.env                        portable non-secret app policy
/etc/kaori/secrets.env                    credentials, mode 0600
/etc/kaori/deploy.env                     deployment adapter only
/var/lib/kaori/deploy-state/release.env   generated immutable release identity
/etc/kaori/trust/ldaps/ca.pem             approved public LDAP CA/chain
/etc/kaori/trust/vault/ca.pem             approved public Vault CA/chain
```

**Do not use** `/workspace/kaori/secrets/trust/`, root `.env`,
`.env.production.example` or the DevContainer
`compose.host-overrides.yml` on a production host.

### 2.1 Provision host trust directory

The existing `deploy/server/bootstrap-host.sh` now prepares the
**empty** `/etc/kaori/trust` directory on governed host initialization.
On an existing server, an authorized operator can prepare it separately
during an approved maintenance/change window:

```bash
sudo install -d -m 0755 /etc/kaori/trust/ldaps /etc/kaori/trust/vault
sudo install -m 0644 approved-ldap-issuing-ca.pem /etc/kaori/trust/ldaps/ca.pem
sudo install -m 0644 approved-vault-issuing-ca.pem /etc/kaori/trust/vault/ca.pem
```

Only copy the **approved public trust chains**. The CA folder must not
contain private keys, secrets, or credentials. For a controlled rotation,
back up the old CA PEM under the approved host recovery procedure, validate
the new PEM and its issuer/hostname chain before replacing it. Use read-only
container mounts, with `create_host_path: false` so missing host trust
directories cannot be silently created by Docker.

### 2.2 Configure scoped production environment

Set the following in `/etc/kaori/app.env` **only when the corresponding
provider is actually enabled**:

```dotenv
# Optional; blank means ldap3/Python uses the system trust store.
KAORI_LDAP_CA_BUNDLE=/run/kaori/trust/ldaps/ca.pem

# Vault allowed origins are exact HTTPS origins, not host aliases.
INTEGRATION_VAULT_ALLOWED_ORIGINS=https://vault.example.internal:8200
INTEGRATION_VAULT_CA_BUNDLE=/run/kaori/trust/vault/ca.pem
```

The hostname `vault.example.internal` is illustrative; use the approved
production Vault certificate name. Never reuse local
`https://host.docker.internal:29820` as a production default.
Keep the existing LDAP bind credential **only** in
`/etc/kaori/secrets.env` as `KAORI_LDAP_BIND_PASSWORD`; do not put
password values in `app.env`, Compose YAML, Git, issues or screenshots.
Vault AppRole RoleID/SecretID are provided only through the existing
encrypted integration connection workflow, not by printing them to logs.

The canonical `deploy/server/compose.server.yml` mounts
`/etc/kaori/trust` at `/run/kaori/trust` read-only for exactly the
`web`, `validation-worker` and `runtime-worker` containers.
`web` handles LDAP provider Test Connection, user sign-in and Vault
connection tests. The Vault validation/runtime workers also need the
trust bundle. This mount **does not replace** the existing
`/app/instance` named volume. PostgreSQL, Redis, deployment bootstrap
and other unrelated workers are not granted the trust mount.

### 2.3 Validate render and runtime reachability safely

Run under the approved deployment identity, with the same deployment
env and generated immutable release identity as a governed deployment.
The following is a **read-only render check** and prints only volume
metadata; it does not publish the full Compose config including secrets:

```bash
docker compose --env-file /etc/kaori/deploy.env \
  --env-file /var/lib/kaori/deploy-state/release.env \
  -f compose.production.yml -f deploy/server/compose.server.yml \
  config --format json \
  | jq '{web:.services.web.volumes,validation:.services["validation-worker"].volumes,runtime:.services["runtime-worker"].volumes}'
```

Confirm all three contain `/etc/kaori/trust` to
`/run/kaori/trust` **read-only**, and `web` retains the
`/app/instance` named volume. Do not print resolved environment
entries; they may include credentials. Some deployment environments
load release variables via shell exports rather than the second env
file; use the canonical governed deployment context when applicable.

After a controlled approved rollout/recreation, from the actual `web`
container check file readability, internal DNS and TLS:

```bash
test -r /run/kaori/trust/ldaps/ca.pem
getent ahostsv4 adds.kaori.cloud
```

If OpenSSL exists, use:

```bash
openssl s_client -connect adds.kaori.cloud:636 \
  -servername adds.kaori.cloud \
  -CAfile /run/kaori/trust/ldaps/ca.pem \
  -verify_hostname adds.kaori.cloud -verify_return_error </dev/null
```

The KAORI image may not contain OpenSSL or `curl` CLI; do not
change the immutable image only for debugging. An approved short-lived
diagnostic environment with the same egress/trust may be used for TLS
inspection. For a Python-only reachability check in the actual runtime
(no bind secret is printed), use:

```bash
python -c 'import socket; print(socket.getaddrinfo("adds.kaori.cloud", 636, type=socket.SOCK_STREAM)[0][4])'
```

Separately verify the Vault FQDN and trust from both
`validation-worker` and `runtime-worker` before claiming provider
readiness. A successful DNS/transport check is not LDAP bind success.

### 2.4 Apply through governed deployment and retain rollback

- Preserve the existing host `app.env`, `secrets.env`, provider-trust
  directory, approved DNS configuration and last known good image digest.
- Apply changes only through the existing reviewed release/rollback
  procedure: environment edits alone do **not** reload a running
  container's process environment. A scoped container recreation is
  required for new mounts, host aliases or environment. Do not
  `docker compose down --volumes`, remove PostgreSQL/Redis volumes,
  or hot-edit a running container's `/etc/hosts`.
- Validate web health and identity provider Test Connection with
  **Enabled OFF**. Validate service-account bind and Base DN search,
  then Save/Validate, provisioning and human-approved login UAT.
  For Vault, run Test Connection → Full Validation → Runtime Refresh,
  preserving evidence separation.
- If any check fails, leave external authentication disabled, restore
  the previous approved CA/env/DNS values and last accepted deployment
  via the existing rollback mechanism, then verify local Database login,
  web/worker readiness and intact provider evidence. Never weaken
  `ssl.CERT_REQUIRED`.

## 3. Private DNS options and decision rule

**Default:** register an authoritative FQDN in AD/private DNS, allow the
production host/resolver to query it, and ensure firewall egress to
the LDAP or Vault service. If `getent ahostsv4` returns no answer,
fix the upstream DNS server, VPN/VPC routing or conditional forwarding.
A Compose static host alias is a time-bounded exception only when
the authoritative resolver cannot be made reachable immediately.

For a **governed Docker Compose server**, a temporary `extra_hosts`
mapping must be service-scoped to the actual application process
(`web` for LDAP), retained in deployment-reviewed infrastructure
configuration and applied consistently by the canonical deploy and
rollback entry points. An operator must not create an ad hoc third
Compose file that the governed `deploy.sh` does not consume. If
production needs this exception, first implement a separately reviewed
adapter workstream; the DevContainer-only ignored override cannot be
promoted as-is. Record ownership, hostname, approved IP, planned
expiry, change ticket, restart scope and rollback.

## 4. Kubernetes reference (not an active KAORI production adapter)

When a future approved KAORI deployment runs on Kubernetes, use:

1. External corporate/AD DNS remains authoritative. Cluster DNS
   (CoreDNS or managed DNS) forwards the required **private zone** to
   the approved internal resolver under an infrastructure change.
   Example conceptual CoreDNS zone (replace domain and IP; do not
   overwrite the existing Corefile or forward all cluster domains):

   ```text
   ad.example.internal:53 {
       errors
       cache 30
       forward . 192.0.2.53
   }
   ```

2. Distribute **public** CA PEM through an approved ConfigMap
   (or organization-managed trust distributor) to only the pods that
   need it, mounted read-only and keyed by the expected filename.
   Environment references `KAORI_LDAP_CA_BUNDLE` or
   `INTEGRATION_VAULT_CA_BUNDLE` must point to the mounted path,
   **not** the DevContainer or server-host path.
   Example **Pod template fragment** (not a deployable KAORI manifest):

   ```yaml
   spec:
     template:
       spec:
         containers:
           - name: web
             volumeMounts:
               - name: ldap-trust
                 mountPath: /run/kaori/trust/ldaps
                 readOnly: true
             env:
               - name: KAORI_LDAP_CA_BUNDLE
                 value: /run/kaori/trust/ldaps/ca.pem
         volumes:
           - name: ldap-trust
             configMap:
               name: approved-ldap-ca
               items:
                 - key: ca.pem
                   path: ca.pem
   ```

3. Only when corporate DNS is unavailable and the endpoint is
   demonstrably static, an explicitly reviewed scoped Pod
   `spec.hostAliases` may be deployed by GitOps/Helm to the
   required workloads, not manually written into `/etc/hosts`.
   It requires a rollout and will become stale when IPs change.
4. Validate DNS/TCP/TLS/identity from the actual web Pod;
   separately validate Vault consumers, network policies, CoreDNS
   performance, unchanged cluster DNS behavior, and a rollback.
   Any cluster DNS/security-sensitive change requires Full Admission
   and UAT evidence, not merely CI.

## 5. Acceptance record

Keep an evidence record with: source issue/PR, approved DNS owner
and forwarder/record, endpoint FQDN and port, authorized CA chain
fingerprint and expiration, host/pod CA file readability, read-only
mount proof, Test Connection result, bind result, producer/worker
status, reviewer/approver, observed rollout SHA and rollback plan.
Never include LDAP bind password, Vault SecretID/token or any private
key in captured evidence. For the lab's older self-signed leaf, also
record its exceptional trust status rather than calling it a CA.

No live production DNS, directory certificate, Compose deployment,
host configuration, or Kubernetes resource was changed by this
documentation workstream.
