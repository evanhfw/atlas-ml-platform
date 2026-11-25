# Deployment and operations

Containerized deployment: multi-stage image, one-shot migration job, hardened
`app` service, TLS at a reverse proxy, API keys, backups, rollback, and
troubleshooting. If this page and `docker-compose.yml`, `Dockerfile`, or
`deploy/*.sh` disagree, the files win.

## 1. Prerequisites and configuration

Docker Engine with Compose v2, network access to pull the pinned base image,
`.env` in the repository root (Compose requires it via `env_file`), and a
TLS-terminating reverse proxy such as Caddy. Jaeger, Prometheus, and Grafana
are optional local observability services.

The image uses `python:3.12-slim` pinned by digest. `uv` exists only in the
builder stage; the runtime runs Python 3.12 as `10001:10001`, installs
dependencies and the project as wheels into `/app/.venv`, and has no build
tooling. Migrations never run at entrypoint or app startup.

Required `.env` values:

| Variable | Purpose |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | PostgreSQL init and credentials |
| `S3_ACCESS_KEY`, `S3_SECRET_KEY` | SeaweedFS S3 credentials |
| `API_KEY_READ` | Read key, at least 32 characters |
| `API_KEY_WRITE` | Mutating key, at least 32 characters, different from the read key |
| `TRUSTED_ARTIFACT_CHECKSUMS` | Comma-separated SHA-256 hex checksums allowed for deserialization |

Production is validated at process start: with `APP_ENV=production` the app
requires `AUTH_ENABLED=true`, `DEBUG=false`, `ARTIFACT_TRUST_POLICY=allowlist`,
and distinct API keys of at least 32 characters. The compose
`x-app-environment` anchor sets those values, overrides user `.env` entries
for `app` and `migrate`, rewrites `DATABASE_URL` to the compose hostname
`postgres`, and sets `S3_ENDPOINT=seaweedfs:8333`. It also sets
`DOCS_ENABLED=false`, removing `/docs`, `/redoc`, and `/openapi.json` from the
production surface.

```bash
openssl rand -hex 32   # API_KEY_READ
openssl rand -hex 32   # API_KEY_WRITE
```

Only checksums listed in `TRUSTED_ARTIFACT_CHECKSUMS` can be loaded for
inference; add one only after validating the artifact.

## 2. Build and start

```bash
docker compose --profile app up -d --build
```

The `app` profile includes `migrate` and `app`. Compose waits for `postgres`
and `seaweedfs` to be healthy, runs `migrate` (`alembic upgrade head`,
`restart: "no"`) to successful completion, then starts `app`.

Both services build the same `runtime` target and share
`atlas-ml-platform:${IMAGE_TAG:-local}`; pin `IMAGE_TAG` per release.
Migrations are separate and observable on purpose: running them in the app
entrypoint would race replicas, hide migration failure inside a web process,
and apply changes without an operator-visible step.

```bash
docker compose --profile app ps -a     # migrate exit code matters
docker compose logs -f migrate
docker compose logs -f app
curl -fsS http://127.0.0.1:8000/api/v1/health/ready
```

A non-zero `migrate` exit means `app` was not started. The healthcheck probes
`/api/v1/health/ready`, which checks PostgreSQL and object storage, not just
the process. Avoid `docker compose down -v` outside disposable development
(it deletes the PostgreSQL and SeaweedFS volumes).

## 3. TLS and reverse proxy

The app does not terminate TLS or read `X-Forwarded-*` headers. Bind it to
loopback (compose publishes `127.0.0.1:8000`) and let a reverse proxy own the
public listener, certificates, access logs, and rate limiting.

Caddy example (`/etc/caddy/Caddyfile`), replacing `atlas.example.com`:

```caddyfile
atlas.example.com {
    encode zstd gzip
    @metrics path /metrics
    respond @metrics 404
    reverse_proxy 127.0.0.1:8000 {
        header_up Host {host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

Caddy renews certificates automatically. The `/metrics` matcher above prevents
public scraping while Prometheus scrapes `127.0.0.1:8000` on the host. Do not
publish `8000` on `0.0.0.0`.
Proxy-to-app traffic can stay plain HTTP on loopback; for another host or
container, use a private network, TLS for that hop, and allow only the proxy to
reach the app. The app has no proxy allowlist or trusted-proxy setting.

## 4. API authentication

Clients send `X-API-Key`; the middleware applies to `/api/v1/*` when
`AUTH_ENABLED=true` (always in production).

| Caller | Key | Allowed |
|---|---|---|
| Read client | `API_KEY_READ` | `GET`/`HEAD`/`OPTIONS` and `POST /api/v1/models/{model_id}/predictions` |
| Writer | `API_KEY_WRITE` | Everything read can do, plus mutations (create models, upload artifacts, create/activate versions) |
| Unauthenticated | none | `/api/v1/health`, `/api/v1/health/ready`, `/metrics` |

```bash
# Read: list models
curl -fsS https://atlas.example.com/api/v1/models -H "X-API-Key: $API_KEY_READ"
# Read: prediction (POST, but read-authorized)
curl -fsS -X POST \
  https://atlas.example.com/api/v1/models/$MODEL_ID/predictions \
  -H "X-API-Key: $API_KEY_READ" -H "Content-Type: application/json" \
  -d '{"features": [[1.0, 2.0, 3.0]]}'
# Write: create a model
curl -fsS -X POST https://atlas.example.com/api/v1/models \
  -H "X-API-Key: $API_KEY_WRITE" -H "Content-Type: application/json" \
  -d '{"name": "classifier", "framework": "sklearn", "task_type": "classification"}'
# Write: upload an artifact; reference the returned uri when creating a version
curl -fsS -X POST https://atlas.example.com/api/v1/artifacts \
  -H "X-API-Key: $API_KEY_WRITE" -F "file=@model.joblib"
```

Missing or unknown key: `401 unauthorized`. Read key used for a mutation:
`403 forbidden`. Keys are compared in constant time and never belong in logs,
shell history, issue trackers, or build args. The compose production profile
sets `DOCS_ENABLED=false`, so `/docs`, `/redoc`, and `/openapi.json` are not
routes. If you re-enable docs, those paths bypass the middleware; restrict them
at the proxy if the schema should not be public.

## 5. Runtime hardening and capacity

`app` runs with `read_only: true` plus a `/tmp` tmpfs, `cap_drop: [ALL]`,
`no-new-privileges:true`, `mem_limit: 1g`, `cpus: "2.0"`, and
`stop_grace_period: 30s`. The image gives uvicorn a 30-second graceful-shutdown
timeout; the app's own drain window is `SHUTDOWN_GRACE_SECONDS` (20 seconds in
compose). It runs one uvicorn worker (`CMD` has no `--workers`).

The image writes no bytecode (`PYTHONDONTWRITEBYTECODE=1`) and the app does not
write into its working directory. Upload size is bounded by
`ARTIFACT_MAX_SIZE_BYTES`; model memory by `MODEL_CACHE_MAX_ENTRIES`.

Scale with more app replicas behind the proxy, not workers per container. Each
replica gets its own pool (`DB_POOL_SIZE=5` plus `DB_MAX_OVERFLOW=10`, up to 15
connections), so budget against PostgreSQL `max_connections` and tune the pool
in `.env`; tune `mem_limit` from observed usage.

## 6. Backup and restore

`deploy/` scripts are the source of truth for flags and behavior. `backup.sh`
takes a validated PostgreSQL custom-format dump and archives the SeaweedFS data
volume. It quiesces `app` and `seaweedfs` by default (`QUIESCE=true`) for a
consistent object archive, causing a short write outage.

```bash
deploy/backup.sh                              # destination ./backups
BACKUP_DIR=/srv/backups/atlas deploy/backup.sh
```

Each run writes the dump, volume archive, and a manifest with paths and
SHA-256 digests. Copy backups off-host. For production object storage, also
use provider versioning or snapshots; a local volume tar is not a substitute
for provider durability. Verify a backup before trusting it:

```bash
BACKUP_DIR=${BACKUP_DIR:-backups}
ls -lh "$BACKUP_DIR" && cat "$BACKUP_DIR"/manifest-*.txt
docker compose exec -T postgres pg_restore --list < "$BACKUP_DIR"/postgres-*.dump >/dev/null
tar -tzf "$BACKUP_DIR"/seaweedfs-*.tar.gz >/dev/null
```

Restore is destructive: it replaces database objects and, by default, the
SeaweedFS volume. The script requires `CONFIRM_RESTORE=yes` and refuses to
restore into `atlas_test`.

Restore drill into a scratch database, leaving objects untouched:

```bash
RESTORE_DATABASE=atlas_restore_test RESTORE_OBJECTS=false CONFIRM_RESTORE=yes \
  deploy/restore.sh
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d atlas_restore_test -c "\dt"'
docker compose exec postgres sh -c 'dropdb -U "$POSTGRES_USER" --if-exists atlas_restore_test'
```

Full restore into the configured database and SeaweedFS volume:
`CONFIRM_RESTORE=yes deploy/restore.sh`. The script stops `app` (and SeaweedFS
when restoring objects), restores the latest dump/archive in `BACKUP_DIR`, and
restarts what was running. Run drills on a schedule and verify readiness,
logs, and a read-only call afterwards.

## 7. Rollback

Use immutable tags: build and push each release as
`atlas-ml-platform:<release>`, deploy with `IMAGE_TAG=<release>`, and never
overwrite a released tag; `migrate` and `app` must share it.

Migrations follow expand/contract: first add columns/tables/indexes
backwards-compatibly, then deploy code writing both shapes (or reading the new
one), and only in a later release drop the old shape, once the previous app
version can no longer run.

Never auto-downgrade data. Rolling back the app image is safe only while its
schema expectations hold, which one expand/contract step guarantees. Do not run
`alembic downgrade` routinely; destructive schema rollback is separate,
reviewed, and needs a fresh backup.

```bash
docker compose --profile app stop app
IMAGE_TAG=<previous-release> docker compose --profile app up -d --no-deps --no-build app
docker compose --profile app ps app
curl -fsS http://127.0.0.1:8000/api/v1/health/ready
```

Leave PostgreSQL and SeaweedFS data in place. `--no-deps` avoids rerunning the
old release's `migrate` through the dependency chain, and `--no-build` avoids
silently rebuilding under the old tag. Do not re-run `migrate` for the old tag
unless its migrations match the current schema.

Restore from backup only when data was corrupted or a destructive migration
cannot be corrected forward. It discards later writes and is the last resort.

## 8. Health, observability, and failure modes

```bash
curl -fsS http://127.0.0.1:8000/api/v1/health          # liveness, no dependencies
curl -fsS http://127.0.0.1:8000/api/v1/health/ready    # readiness: DB + S3
curl -fsS http://127.0.0.1:8000/metrics | head         # Prometheus, unauthenticated
docker compose --profile app ps
docker compose logs --since=15m app migrate postgres seaweedfs
```

Prometheus scrapes `127.0.0.1:8000/metrics`; Jaeger UI is on `16686`, Grafana
on `3002`, and OTLP traces go to `http://jaeger:4318`.

| Symptom | Check |
|---|---|
| `401 unauthorized` / `403 forbidden` | Missing/wrong key, or a read key used for a mutation; use `API_KEY_WRITE` for writes |
| `503`, `checks.database=error` | PostgreSQL down, unreachable, or schema/credentials wrong; check `postgres` health and `migrate` logs |
| `503`, `checks.artifact_store=error` | SeaweedFS down or bucket/credentials mismatch |
| `app` never starts | `migrate` exited non-zero, a dependency is unhealthy, or settings validation failed; use `ps -a` and logs |

## 9. Secret handling

- Inject secrets through the environment (`.env` read by Compose, or an
  external secret manager). Never bake `.env` or keys into the image;
  `.dockerignore` excludes `.env` and `.env.*` from the build context.
- Keep `.env` mode `600`, owned by the deploying user. Services read it as the
  invoking user; the app process runs as `10001:10001`.
- Never pass keys as build args, image labels, or command-line arguments that
  land in `ps` or shell history. Rotate immediately after suspected exposure.
- Rotate `API_KEY_READ`/`API_KEY_WRITE` by updating `.env` and recreating the
  app (`docker compose --profile app up -d --no-deps app`); rotation is not
  hot-reloaded and both keys must stay at least 32 characters and distinct.
- Backups contain full data and use `umask 077`; keep the directory private and
  encrypt off-host copies.
