# Running KAORI

This file is the operational reference for local development and container-based production releases.

## Development with VS Code Dev Container

### First start

1. Start Docker Desktop.
2. Open the KAORI repository in VS Code.
3. Copy the environment template on the host:

   ```powershell
   Copy-Item .env.example .env
   ```

4. In `.env`, use the Docker service names:

   ```dotenv
   APP_ENV=development
   DATABASE_URL=postgresql://postgres:<password>@db:5432/kaori
   REDIS_URL=redis://redis:6379/0
   RATELIMIT_STORAGE_URI=redis://redis:6379/2
   ```

5. Run **Dev Containers: Rebuild Without Cache and Reopen in Container**.
6. In the Dev Container terminal, initialize a fresh database and the first administrator:

   ```bash
   bash scripts/init_db.sh --bootstrap-admin
   ```

7. Start the Tailwind watcher in one terminal:

   ```bash
   npm run watch-css
   ```

8. Press `F5` and select **KAORI: Flask Auto Reload**, or run:

   ```bash
   bash scripts/run_dev.sh
   ```

9. Open <http://localhost:5000>.

### Daily development

Use **Dev Containers: Reopen in Container**, then run:

```bash
npm run watch-css
```

Start Flask using `F5`. Do not create or activate a Windows `.venv`.

### Reset the development database

Run this from the host after reopening the folder locally:

```powershell
docker compose `
  -f compose.yml `
  -f .devcontainer/compose.devcontainer.yml `
  down --volumes --remove-orphans
```

Rebuild the Dev Container, then run:

```bash
bash scripts/init_db.sh --bootstrap-admin
```

---

## Production release

Production does not use the Dev Container or the Flask development server. It runs an immutable image through Gunicorn.

### 1. Build and publish the image

The included GitHub workflow builds on tags matching `v*` and pushes to GHCR. Create a release tag:

```bash
git tag -a v1.0.0 -m "KAORI v1.0.0"
git push origin v1.0.0
```

Alternatively, build and push manually:

```bash
docker build --target production -t ghcr.io/<organization>/kaori:v1.0.0 .
docker push ghcr.io/<organization>/kaori:v1.0.0
```

### 2. Prepare the production host

Create a protected deployment directory:

```bash
sudo mkdir -p /opt/kaori
sudo chown "$USER":"$USER" /opt/kaori
cd /opt/kaori
```

Copy only these deployment files to the host:

```text
compose.production.yml
.env.production
```

Create the environment file:

```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

Set at least:

```dotenv
KAORI_IMAGE=ghcr.io/<organization>/kaori:v1.0.0
APP_VERSION=1.0.0
SECRET_KEY=<64-or-more-random-characters>
TRUSTED_HOSTS=kaori.example.com,127.0.0.1,localhost
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
RATELIMIT_STORAGE_URI=redis://...
```

Generate a secret example:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

Log in to a private registry when required:

```bash
docker login ghcr.io
```

### 3. Pull and validate

```bash
docker compose --env-file .env.production -f compose.production.yml pull

docker compose --env-file .env.production -f compose.production.yml run --rm validate
```

Fix every validation error before continuing.

### 4. Backup and migrate

Back up PostgreSQL before every upgrade using the database platform's supported backup procedure. Then run migration exactly once:

```bash
docker compose --env-file .env.production -f compose.production.yml run --rm migrate
```

### 5. Bootstrap the first administrator

Only on the first installation, temporarily set `ADMIN_USERNAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` in `.env.production`, then run:

```bash
docker compose --env-file .env.production -f compose.production.yml run --rm web \
  flask --app run:app bootstrap-admin
```

Remove `ADMIN_PASSWORD` from `.env.production` immediately afterward.

### 6. Start or upgrade KAORI

```bash
docker compose --env-file .env.production -f compose.production.yml up -d web
```

Verify:

```bash
docker compose --env-file .env.production -f compose.production.yml ps

docker compose --env-file .env.production -f compose.production.yml logs --tail=200 web

curl --fail http://127.0.0.1:5000/health/live
curl --fail http://127.0.0.1:5000/health/ready
```

### 7. Configure HTTPS reverse proxy

KAORI binds to `127.0.0.1:5000` by default. Copy `deploy/nginx/kaori.conf.example` to the host Nginx configuration, replace the hostname and certificate paths, validate, then reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Verify externally:

```bash
curl --fail https://kaori.example.com/health/ready
```

### Release update

Change `KAORI_IMAGE` and `APP_VERSION` in `.env.production`, then run:

```bash
docker compose --env-file .env.production -f compose.production.yml pull

docker compose --env-file .env.production -f compose.production.yml run --rm validate

docker compose --env-file .env.production -f compose.production.yml run --rm migrate

docker compose --env-file .env.production -f compose.production.yml up -d web
```

Do not run `bootstrap-admin` again.

### Application rollback

Set `KAORI_IMAGE` back to the previous immutable tag and run:

```bash
docker compose --env-file .env.production -f compose.production.yml pull

docker compose --env-file .env.production -f compose.production.yml up -d web
```

Database rollback is separate. Restore a tested database backup only when the migration itself is not backward compatible.
