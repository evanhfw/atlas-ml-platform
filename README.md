# Atlas ML Platform

A production-oriented ML model management and serving platform, built as a
modular monolith with Clean Architecture boundaries.

Current scope: FastAPI application foundation, validated settings, async
PostgreSQL lifecycle, health endpoints, and Alembic migrations.

Product requirements and roadmap: [`prd.md`](prd.md).

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker with Compose

## Setup

1. Create the local environment file:

   ```bash
   cp .env.example .env
   ```

   Set `POSTGRES_PASSWORD` and make the password in `DATABASE_URL` match it.
   The defaults target `atlas_dev` on `localhost:5432`. `.env` is gitignored;
   never commit real credentials.

2. Install dependencies:

   ```bash
   uv sync
   ```

3. Start PostgreSQL:

   ```bash
   docker compose up -d
   docker compose ps
   ```

   Wait until the container is `healthy` and the port mapping shows
   `127.0.0.1:5432->5432/tcp`.

4. Apply migrations to the development database:

   ```bash
   uv run alembic upgrade head
   ```

5. On a fresh volume, Compose creates both `atlas_dev` and `atlas_test`.
   `atlas_dev` comes from `POSTGRES_DB`; `atlas_test` is created by
   `docker/postgres/init/01-create-test-db.sh`.

   Initialization scripts run only when the PostgreSQL data directory is
   empty. For a volume created before this script existed, create the test
   database manually:

   ```bash
   docker compose exec postgres \
     psql -U atlas -d postgres -c 'CREATE DATABASE atlas_test OWNER atlas;'
   ```

   `atlas_test` is separate from `atlas_dev` on purpose.

## Run

```bash
uv run uvicorn atlas_ml_platform.main:app --reload
```

- API docs: <http://127.0.0.1:8000/docs>
- Liveness: `GET /api/v1/health`
- Database probe: `GET /api/v1/health/database`

`/api/v1/health` does not touch PostgreSQL. `/api/v1/health/database` returns
`503` when the database is unreachable.

## Tests

```bash
uv run pytest
```

Tests use `atlas_test`, never `atlas_dev`. `tests/conftest.py` fails closed if
the target database name is not `atlas_test`.

Override the test database with:

```bash
export TEST_DATABASE_URL="postgresql+asyncpg://atlas:CHANGE_ME@localhost:5432/atlas_test"
uv run pytest
```

Use the same password as `POSTGRES_PASSWORD`.

Alembic reads `DATABASE_URL`, not `TEST_DATABASE_URL`. To migrate the test
database:

```bash
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
```

## Migrations

```bash
uv run alembic current        # applied revision
uv run alembic upgrade head   # apply pending migrations
uv run alembic check          # fail if metadata and database drift
```

Create a migration after changing ORM models:

```bash
uv run alembic revision --autogenerate -m "describe change"
```

Review the generated file before applying it. `Base.metadata` is built from
`infrastructure/database/models.py`; new model modules must be imported by
`migrations/env.py`, otherwise autogenerate cannot see them.

Test upgrade and downgrade against `atlas_test`, not the development database:

```bash
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic downgrade base
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
```

## Quality gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

## Destructive operations

```bash
docker compose down -v
```

This deletes the `atlas_postgres_data` volume, including `atlas_dev` and
`atlas_test`. It cannot be undone. On the next `docker compose up -d`, the
init script recreates both databases; migrations must be applied again.

## Layout

```text
src/atlas_ml_platform/
├── api/                 # HTTP routes and dependencies
├── core/                # application factory and lifespan
├── infrastructure/
│   └── database/        # engine, sessions, ORM base
├── modules/
│   └── model_registry/
│       ├── domain/      # entity and value objects
│       ├── application/ # ports and use cases
│       └── infrastructure/  # ORM model, repository, unit of work
└── config.py            # typed settings

docker/
└── postgres/init/       # local-only database bootstrap scripts

migrations/              # Alembic environment and revisions
tests/
├── unit/                # domain/application tests
├── integration/         # real PostgreSQL tests
└── e2e/                 # API tests through the ASGI app
```
