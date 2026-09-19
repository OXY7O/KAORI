# KAORI VPS Compose-Managed Ingress and TLS Design

## Context

Issue #49 already proved the full KAORI application graph on the UAT VPS using an immutable RC and private PostgreSQL/Redis state. Issue #50 owns the public edge. The earlier #50 draft used host Nginx + host Certbot, but the approved design now moves the complete HTTP/TLS edge into the governed Docker Compose topology.

DNS authority is already configured for the UAT apex:

```text
kaori.cloud A 62.171.187.206
```

The target is that an ordinary governed KAORI deployment can bring up the application, Nginx, Certbot, certificate state, renewal loop, and public verification without installing Nginx or Certbot on the host OS.

## Goals

- Serve KAORI at `https://kaori.cloud` through a Compose-managed Nginx service.
- Remove the KAORI web host-port publication entirely; Nginx reaches `web:5000` over `kaori_production` Docker DNS.
- Keep PostgreSQL and Redis private with no host-published ports.
- Publish only Nginx HTTP/HTTPS ports from the application stack: host `80 -> nginx:8080` and `443 -> nginx:8443`.
- Obtain and renew a Let's Encrypt certificate using a Compose-managed Certbot service and shared named volumes.
- Allow the first Nginx start before a certificate exists by using an HTTP-only ACME configuration, then reload automatically into the final TLS configuration after Certbot writes the certificate.
- Reload Nginx after certificate renewal without mounting `/var/run/docker.sock` or granting host sudo.
- Reject unexpected HTTP Host and TLS SNI traffic rather than forwarding it to KAORI.
- Preserve the proxy identity headers expected by KAORI and keep CSP ownership in the application.
- Require immutable digest-qualified images for KAORI, PostgreSQL, Redis, Nginx, and Certbot.
- Produce concise KAORI-standard deployment/verification output with visual status markers.

## Non-goals

- DNS provider mutation remains operator-owned.
- Host firewall and SSH daemon policy remain host infrastructure. Compose does not mutate firewall or SSH configuration.
- Stable `main` promotion remains Issue #51 and still requires explicit human UAT acceptance.
- No Docker socket is mounted into Nginx, Certbot, or any application container.

## Architecture

```text
Internet
   |
   | TCP 80 / 443
   v
Docker host publication
   | 80  -> nginx:8080
   | 443 -> nginx:8443
   v
Nginx container
   |-- unknown Host/SNI -> reject
   |-- /.well-known/acme-challenge/ -> shared ACME webroot
   `-- kaori.cloud HTTPS -> http://web:5000
                               |
                               v
                            KAORI web

Certbot container
   |-- first `certonly --webroot`
   |-- recurring `certbot renew`
   `-- writes shared Let's Encrypt + ACME volumes

PostgreSQL / Redis -> `kaori_production` network only, no host ports
KAORI web            -> `kaori_production` network only, no host port
```

## Compose topology

`compose.production.yml` remains the canonical application graph. The `web` service exposes container port 5000 to the Compose network but does not publish it to the host.

`deploy/vps/compose.vps.yml` extends the graph with:

- `postgres`;
- `redis`;
- `nginx`;
- `certbot`;
- persistent named volumes for PostgreSQL, Redis, Let's Encrypt state, and the ACME webroot.

Nginx and Certbot images are long-lived infrastructure dependencies configured in `/etc/kaori/.env.production` using digest-qualified references.

## Nginx lifecycle

`deploy/nginx/nginx-entrypoint.sh` is the Nginx PID 1 wrapper.

1. Validate `KAORI_PUBLIC_DOMAIN` and required templates.
2. If the certificate does not yet exist, render `kaori-http.conf.template` and start Nginx on port 8080. This configuration serves the ACME webroot only for the intended hostname and rejects unknown hosts.
3. Monitor `/etc/letsencrypt/live/<domain>/fullchain.pem` and `privkey.pem`.
4. When the certificate appears, render `kaori.conf.template`, validate it with `nginx -t`, and reload Nginx into the TLS configuration.
5. When certificate material changes after renewal, validate and reload again.

The final TLS template listens on container port 8443, supports TLS 1.2/1.3, rejects unknown SNI, adds HSTS, and proxies only to `http://web:5000`.

The Nginx root master exists only inside the container so it can read Certbot-managed private-key material. The container uses a read-only root filesystem, `no-new-privileges`, all Linux capabilities dropped, no Docker socket, and unprivileged internal ports 8080/8443.

## Certbot lifecycle

`deploy/nginx/certbot-entrypoint.sh` owns certificate issuance and renewal.

- Required environment: `KAORI_PUBLIC_DOMAIN`, `KAORI_LETSENCRYPT_EMAIL`.
- First start uses `certbot certonly --webroot` against `/var/www/certbot`.
- Certificate/account state is retained in the Let's Encrypt named volume.
- Renewal runs periodically (default 12 hours) using `certbot renew --webroot`.
- Nginx discovers certificate changes through the shared read-only certificate volume and reloads itself; Certbot never needs the Docker socket or host service control.

## Persistent operator configuration

The UAT host environment must include:

```dotenv
KAORI_PUBLIC_BASE_URL=https://kaori.cloud
TRUSTED_HOSTS=kaori.cloud,127.0.0.1,localhost
KAORI_PUBLIC_DOMAIN=kaori.cloud
KAORI_PUBLIC_IP=62.171.187.206
KAORI_LETSENCRYPT_EMAIL=<operator ACME email>
KAORI_NGINX_IMAGE=<digest-qualified reviewed Nginx image>
KAORI_CERTBOT_IMAGE=<digest-qualified reviewed Certbot image>
```

`KAORI_BIND_ADDRESS` is no longer part of the VPS production contract because the web service has no host publication.

## Deployment transaction

`deploy/vps/deploy.sh` continues to own the immutable application transaction and extends its ordered stages:

1. validate release identity, persistent environment, and Compose config;
2. authenticate to the registry and pull the exact KAORI image;
3. start/wait for PostgreSQL and Redis;
4. create the pre-migration backup when required;
5. run environment validation and migration;
6. start the complete KAORI application graph;
7. wait for the internal `web` container health check;
8. pull/start immutable Nginx and Certbot dependencies;
9. wait for public HTTPS/TLS readiness;
10. run full application + edge verification;
11. record exact deployment evidence.

A certificate/DNS/edge failure prevents the transaction from being recorded as a successful public UAT deployment, while the application containers may remain healthy for diagnosis.

## Verification

`deploy/vps/verify.sh` proves the internal Compose graph and immutable image identities. It requires:

- all application/state/edge containers running;
- PostgreSQL and Redis healthy and without host ports;
- KAORI `web` has no host-published port;
- the KAORI web health check passes from inside the web container;
- exactly one Beat replica and all worker queues answer introspection;
- Nginx and Certbot are configured with the expected immutable infrastructure images when supplied.

`deploy/nginx/verify-ingress.sh` proves the public boundary:

- DNS resolves to the expected VPS IPv4;
- HTTP redirects to the expected HTTPS hostname;
- HTTPS readiness succeeds;
- certificate SAN contains the domain and has more than seven days remaining;
- HSTS is present;
- host ports 5000, 5432, and 6379 are not listeners;
- expected Nginx host ports 80/443 are listening;
- unknown HTTP Host is rejected;
- unknown TLS SNI is rejected.

## Security boundaries

- `kaori-deploy` remains non-sudo.
- No application/state host ports are published.
- No container receives the Docker socket.
- Nginx and Certbot use immutable image references.
- TLS private keys remain in a Docker named volume and are never committed or uploaded as Actions artifacts.
- Nginx does not replace KAORI CSP.
- Host firewall still must permit public TCP 80/443 and separately govern SSH.

## Failure behavior

- Missing/invalid immutable Nginx or Certbot image -> Compose validation/deploy stops.
- Missing domain/email -> Certbot fails closed.
- DNS/port 80 not reachable -> certificate issuance fails and Nginx stays HTTP-only for diagnosis/retry.
- Invalid TLS template/certificate -> Nginx does not reload the invalid configuration.
- Public HTTPS does not become ready before the deployment timeout -> deployment fails without recording public UAT success.
- Unknown Host/SNI forwarding, unexpected host ports, or near-expiry certificate -> verification fails.

## Acceptance evidence

Issue #50 is complete only when the admitted staging revision is deployed and evidence records:

1. `kaori.cloud -> 62.171.187.206`.
2. Nginx and Certbot are running as Compose services from immutable images.
3. KAORI web, PostgreSQL, and Redis have no host-published ports.
4. `http://kaori.cloud` redirects to HTTPS.
5. `https://kaori.cloud/health/ready` succeeds with a publicly trusted certificate.
6. Unknown Host/SNI is rejected.
7. Certificate renewal configuration is active and a dry-run/manual renewal proof is captured before UAT acceptance.
8. External port/TLS/DAST checks have no unexplained high/critical finding.

Explicit human acceptance of the exact staging SHA + immutable RC digest remains required before Issue #51 promotion.
