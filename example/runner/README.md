# Disposable GitHub Runner Example

This is a **demo-only** self-hosted runner container. It is not the governed production runner topology.

1. Copy `example/.env.example` to `example/.env`.
2. Set `GITHUB_RUNNER_URL` and a short-lived `GITHUB_RUNNER_TOKEN` locally.
3. Set `DOCKER_GID` to the host Docker socket group ID when Docker jobs are required.
4. Start:

```bash
docker compose --env-file example/.env -f example/runner/compose.yml up --build
```

The token is consumed at runtime and is never printed. The Docker socket grants root-equivalent host capability; use this only on a disposable demo host.
