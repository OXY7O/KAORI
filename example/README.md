# KAORI Integration Examples

This directory is the **standalone integration-example boundary** for KAORI. It does not contain production configuration and is never an authority for the real Staging or Production environments.

Each component owns an independent Docker Compose stack. Start only what you need, or use the aggregate stack when you want the full KAORI integration demo.

| Component | Standalone command | Default endpoint |
| --- | --- | --- |
| Prometheus | `docker compose -f example/prometheus/compose.yml up -d` | `http://localhost:9090` |
| Alertmanager | `docker compose -f example/alertmanager/compose.yml up -d` | `http://localhost:9093` |
| MinIO | `docker compose -f example/minio/compose.yml up -d` | API `http://localhost:9000`, Console `http://localhost:9001` |
| Thanos Query | `docker compose -f example/thanos/compose.yml up -d` | `http://localhost:10902` |
| Runner | `docker compose -f example/runner/compose.yml up -d` | disposable self-hosted runner |

## Quick Start — full integration

```bash
cp example/.env.example example/.env
bash example/bin/stack.sh start all
bash example/bin/stack.sh status all
```

The aggregate topology starts Prometheus, Alertmanager, MinIO, a MinIO bucket initializer, Thanos Sidecar, and Thanos Query. Prometheus sends representative demo alerts to Alertmanager and exposes an external label for Thanos. MinIO exposes public demo metrics and provides the S3-compatible `thanos` bucket used by the Sidecar.

## Connect KAORI

Use these values only for the local/disposable example environment:

```text
Prometheus    http://localhost:9090
Alertmanager http://localhost:9093
Thanos Query http://localhost:10902
MinIO/S3     http://localhost:9000
Access key   kaori-demo
Secret key   kaori-demo-secret
```

For KAORI configuration, map these endpoints to the corresponding integration/provider settings. Do not copy real Staging/Production secrets into `example/.env`.

## Standalone behavior

The standalone compose files intentionally avoid dependencies on the other example components:

- **Prometheus** self-scrapes and loads representative KAORI demo rules.
- **Alertmanager** runs with a null receiver and KAORI-style grouping/inhibition semantics.
- **MinIO** runs as an isolated S3-compatible demo server and initializes a `thanos` bucket.
- **Thanos** runs Query by itself to validate the Query API; use the aggregate stack for real fan-out through a Prometheus Sidecar.
- **Runner** is opt-in and disposable. It requires an operator-supplied registration token at runtime and mounts the Docker socket, which is root-equivalent access. Never use this compose as the governed production runner topology.

## Readiness

```bash
bash example/bin/stack.sh status prometheus
bash example/bin/stack.sh status alertmanager
bash example/bin/stack.sh status minio
bash example/bin/stack.sh status thanos
```

The helper prints concise PASS/FAIL evidence and the endpoint that failed. Raw Docker Compose logs remain available with `docker compose ... logs`.

## Stop / reset

```bash
bash example/bin/stack.sh stop all
bash example/bin/stack.sh reset all
```

`reset` removes example volumes. Never point the example compose files at real KAORI state volumes.

## MinIO compatibility note

The MinIO community project changed distribution in 2026 and no longer treats historical prebuilt community containers as a maintained production path. The pinned MinIO image here is therefore a **demo compatibility fixture only**. Override `MINIO_IMAGE` in `example/.env` when your environment maintains an approved S3-compatible image.

## Boundaries

- No `kaori.cloud`, host IP, SSH private key, registry credential, Telegram token, or real integration credential belongs here.
- `example/` is excluded from production runtime artifacts.
- Production deployment remains governed by `deploy/` and GitHub Actions.
- Production runner lifecycle remains governed separately; the runner example is disposable only.
