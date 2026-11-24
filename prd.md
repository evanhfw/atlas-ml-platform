# Atlas ML Platform

## Product Requirements Document (PRD), Technical Vision & Engineering Roadmap

**Document type:** Product + Technical Design + Delivery Roadmap\
**Status:** Living document --- initial baseline\
**Version:** 1.0\
**Last updated:** 23 November 2026\
**Primary implementation approach:** Learning by Building\
**Initial architecture:** Modular Monolith, Clean Architecture,
DDD-inspired modules, Hexagonal Architecture principles

------------------------------------------------------------------------

# 1. Executive Summary

Atlas ML Platform is a production-oriented machine learning model
management and serving platform. The project is intended to demonstrate
the engineering skills required to design, build, operate, and evolve a
reliable backend platform for machine learning workloads.

The platform will provide a foundation for:

-   Registering and managing ML models.
-   Tracking model versions and their lifecycle.
-   Storing model artifacts outside the relational database.
-   Deploying or activating a model version for inference.
-   Exposing prediction APIs.
-   Recording inference metadata and operational metrics.
-   Observing application behavior through logs, metrics, traces, and
    dashboards.
-   Supporting repeatable testing, migrations, deployment, and graceful
    shutdown.

**This is first and foremost a hands-on learning project.** Atlas ML
Platform is the vehicle through which the learner develops production-grade
backend engineering and ML engineering skills. The goal is not merely to
finish features or produce a repository that looks sophisticated. The goal
is to understand why each component exists, how it works, how it interacts
with the rest of the system, what can fail, and how to verify it.

The implementation roadmap is therefore also a curriculum. Each milestone
is a deliberate learning unit and must be completed in small, sequential
steps. A milestone is not complete just because code has been generated or
an endpoint returns a successful response. The learner should be able to
explain the underlying concepts in their own words, trace the execution
flow, debug common failure modes, write or interpret tests, and justify
the chosen design against reasonable alternatives.

Implementation should proceed incrementally. Each milestone must produce
a working, testable result before introducing the next layer of complexity.
Do not skip ahead simply to add more technologies. Prefer a small working
system whose internals are understood over a large system assembled by an
AI agent.

The initial release should favor a well-structured modular monolith over
premature microservices. The architecture must preserve clear module
boundaries so that selected components can be extracted into services
later if actual scaling or organizational needs justify it.

## 1.1 Product vision

Provide a reliable, observable, and extensible control plane and
inference runtime for ML models, with enough production engineering
depth to demonstrate backend engineering and ML engineering
capabilities.

## 1.2 Core product proposition

A user should be able to register a model, upload or reference its
artifact, create versions, select an active version, send inference
requests, and inspect the operational behavior of the system.

## 1.3 Engineering proposition

The project should demonstrate:

-   Python backend engineering with FastAPI.
-   Clean Architecture and modular domain design.
-   PostgreSQL persistence and schema migrations.
-   Async database access and connection lifecycle management.
-   API design, validation, error handling, and versioning.
-   Model artifact management.
-   ML inference integration.
-   Automated testing at multiple levels.
-   Structured logging and observability.
-   Containerized local development and deployment.
-   Reliability practices such as health checks, graceful shutdown, and
    resource cleanup.
-   Capacity planning and performance testing.

------------------------------------------------------------------------

# 2. Goals, Non-Goals, and Success Criteria

## 2.1 Product goals

1.  Provide an API to register and inspect ML models.
2.  Support multiple versions for each model.
3.  Track model metadata, status, and artifact location.
4.  Store model artifacts in object storage rather than PostgreSQL.
5.  Support model selection and inference through a stable API.
6.  Record inference outcomes and operational metadata.
7.  Make the platform observable and diagnosable.
8.  Keep the system testable and maintainable as capabilities grow.

## 2.2 Learning goals

1.  Understand how a production Python service is structured and
    started.
2.  Understand ASGI, FastAPI, Uvicorn, application factories, and
    lifespan management.
3.  Build configuration management that works across development,
    testing, and production.
4.  Understand PostgreSQL, SQLAlchemy 2.x async, connection pools,
    sessions, transactions, and migrations.
5.  Apply Clean Architecture without turning it into unnecessary
    abstraction.
6.  Design domain modules and use cases.
7.  Integrate object storage and ML inference runtimes.
8.  Implement tests that isolate external dependencies.
9.  Instrument the system using OpenTelemetry.
10. Export metrics to Prometheus and visualize them in Grafana.
11. Understand distributed tracing, structured logs, and correlation
    IDs.
12. Learn production operations: graceful shutdown, readiness, liveness,
    timeouts, retries, and resource limits.

## 2.3 Non-goals for the initial release

The initial release will not attempt to:

-   Build a full multi-tenant enterprise SaaS product.
-   Implement Kubernetes orchestration before a working application
    exists.
-   Split every domain module into a separate microservice.
-   Build a general-purpose workflow orchestration engine.
-   Support every ML framework or arbitrary user-provided Python code.
-   Implement a feature store.
-   Implement online model training.
-   Guarantee GPU inference or autoscaling in the first release.
-   Build a complex frontend before the backend API and domain model are
    stable.
-   Introduce Kafka, service mesh, or distributed transactions without a
    demonstrated requirement.

These may become future extensions.

## 2.5 Definition of success

The project is successful when:

-   A developer can clone the repository and run the stack using
    documented commands.
-   The API starts with validated configuration and manages its
    resources correctly.
-   PostgreSQL connectivity and migrations work reliably.
-   Model metadata and versions can be created, retrieved, and updated
    through the API.
-   Model artifacts can be stored and retrieved from object storage.
-   An inference request can be routed to a selected model version.
-   Tests run against isolated test infrastructure and cannot
    accidentally mutate development data.
-   Logs, metrics, and traces provide enough context to investigate a
    failed request.
-   The application shuts down cleanly and releases its resources.
-   The architecture remains understandable and supports incremental
    extension.

------------------------------------------------------------------------

# 3. Users and Primary Use Cases

## 3.1 Primary users

### Platform developer

Builds and operates the platform, configures infrastructure, maintains
APIs, and investigates incidents.

### ML engineer

Registers models, uploads artifacts, configures model versions, and
validates inference behavior.

### API consumer

Sends input data to a deployed model and consumes prediction results.

### Platform operator

Monitors health, latency, error rates, resource utilization, and
model-serving behavior.

## 3.2 Core user journeys

### Journey A --- Register a model

1.  Client submits model metadata.
2.  API validates the request.
3.  Application use case enforces domain rules.
4.  Repository persists the model record.
5.  API returns the model identifier and metadata.

### Journey B --- Create a model version

1.  Client identifies an existing model.
2.  Client supplies version metadata and artifact information.
3.  Platform validates version uniqueness and required metadata.
4.  Artifact is stored in object storage or an existing artifact URI is
    registered.
5.  Version metadata is persisted.
6.  API returns the created version.

### Journey C --- Activate a model version

1.  Client requests activation of a version.
2.  Platform verifies that the model and version exist.
3.  Platform verifies that the version is eligible for activation.
4.  The active-version pointer or deployment record is updated
    transactionally.
5.  The serving layer uses the selected version for subsequent requests.

### Journey D --- Run inference

1.  Client sends an inference request.
2.  API validates the input envelope.
3.  Application resolves the model and active version.
4.  Runtime obtains or loads the required artifact.
5.  Runtime executes prediction.
6.  API returns the prediction and request metadata.
7.  Metrics and logs are emitted; trace context is propagated.

### Journey E --- Investigate an inference failure

1.  Operator identifies an elevated error rate or slow endpoint.
2.  Operator opens a trace or correlated log entry.
3.  Operator identifies the model, version, request path, and failing
    dependency.
4.  Operator uses the evidence to isolate whether the issue is in API
    validation, database access, artifact retrieval, model loading, or
    inference execution.

------------------------------------------------------------------------

# 4. Scope and Functional Requirements

Priority convention:

-   **P0:** Required for the first useful release.
-   **P1:** Important follow-up capability.
-   **P2:** Advanced or optional capability.

## 4.1 Application and API foundation

-   **FR-001 (P0):** The application must expose a versioned API
    namespace, initially `/api/v1`.
-   **FR-002 (P0):** The application must use an application factory
    (`create_app`).
-   **FR-003 (P0):** Startup and shutdown resources must be managed
    through FastAPI lifespan.
-   **FR-004 (P0):** Configuration must be validated at startup.
-   **FR-005 (P0):** The API must provide a basic liveness endpoint.
-   **FR-006 (P0):** The API must provide a readiness endpoint that
    checks critical dependencies.
-   **FR-007 (P1):** API errors must use a consistent response
    structure.
-   **FR-008 (P1):** Requests should have a correlation/request ID.
-   **FR-009 (P1):** API documentation must describe request and
    response schemas.

## 4.2 Model registry

-   **FR-010 (P0):** A client can register a model.
-   **FR-011 (P0):** A client can retrieve a model by ID.
-   **FR-012 (P0):** A client can list models with pagination.
-   **FR-013 (P1):** A client can update permitted model metadata.
-   **FR-014 (P1):** A client can archive or deactivate a model.
-   **FR-015 (P1):** Model names or stable identifiers must follow an
    explicit uniqueness policy.

Suggested model metadata:

-   ID
-   Name
-   Description
-   Framework
-   Task type
-   Input schema or signature reference
-   Output schema or signature reference
-   Owner or creator (later)
-   Created and updated timestamps
-   Lifecycle status

## 4.3 Model versions

-   **FR-020 (P0):** A model can have multiple versions.
-   **FR-021 (P0):** A version has a stable version identifier or
    version number.
-   **FR-022 (P0):** A version stores artifact URI and artifact
    metadata.
-   **FR-023 (P0):** A version stores framework and runtime
    compatibility metadata.
-   **FR-024 (P1):** A version can move through lifecycle states such as
    draft, ready, active, archived, or failed.
-   **FR-025 (P1):** The platform must prevent invalid lifecycle
    transitions.
-   **FR-026 (P1):** The platform must support selecting an active
    version.
-   **FR-027 (P2):** The platform may support aliases such as
    `production`, `staging`, or `champion`.

## 4.4 Artifact management

-   **FR-030 (P0):** Model binaries must not be stored directly in
    PostgreSQL.
-   **FR-031 (P0):** PostgreSQL stores artifact URI, checksum, size,
    format, and related metadata.
-   **FR-032 (P0):** The platform must support an object-storage
    adapter.
-   **FR-033 (P1):** Upload and download operations must validate
    expected metadata.
-   **FR-034 (P1):** Artifact integrity should be verified using a
    checksum.
-   **FR-035 (P2):** Support artifact retention and cleanup policies.

Initial object storage target: SeaweedFS for local development, with an
S3-compatible interface to support later migration to managed object
storage.

## 4.5 Inference

-   **FR-040 (P0):** A client can submit an inference request for a
    registered model.
-   **FR-041 (P0):** The platform resolves the selected model version.
-   **FR-042 (P0):** The platform validates inference input against the
    supported contract.
-   **FR-043 (P0):** The platform returns a structured prediction
    response.
-   **FR-044 (P0):** The platform returns a request or inference ID for
    diagnostics.
-   **FR-045 (P1):** The runtime should avoid loading the same artifact
    for every request.
-   **FR-046 (P1):** Model loading and inference execution must have
    explicit timeout and error behavior.
-   **FR-047 (P1):** The platform should record latency and outcome
    metadata.
-   **FR-048 (P2):** Support batch inference.
-   **FR-049 (P2):** Support asynchronous or long-running inference
    jobs.

## 4.6 Observability and operations

-   **FR-050 (P0):** Application logs must be structured and include
    severity and timestamp.
-   **FR-051 (P0):** The application must expose basic health
    information.
-   **FR-052 (P1):** Instrument HTTP requests and database operations
    with OpenTelemetry.
-   **FR-053 (P1):** Export metrics in a Prometheus-compatible format.
-   **FR-054 (P1):** Provide Grafana dashboards for request rate,
    latency, errors, and resource usage.
-   **FR-055 (P1):** Export traces to a trace backend such as Tempo.
-   **FR-056 (P1):** Correlate logs and traces using trace/request
    identifiers.
-   **FR-057 (P2):** Add alert rules for sustained service degradation.
-   **FR-058 (P2):** Add inference-specific metrics such as model load
    duration and per-model latency.

------------------------------------------------------------------------

# 5. Non-Functional Requirements

## 5.1 Reliability

-   Resources must be created during startup and released during
    shutdown.
-   Startup must fail clearly if a mandatory dependency is unavailable,
    unless a deliberate degraded-startup policy is introduced.
-   Readiness must become unhealthy when critical dependencies are
    unavailable.
-   Liveness must not fail merely because a downstream dependency is
    temporarily unavailable.
-   Database sessions must not be shared concurrently between unrelated
    tasks.
-   External calls must have explicit timeouts.
-   Retries must be bounded and used only where operations are safe to
    retry.
-   Transactions must have clear ownership and boundaries.

## 5.2 Performance

Initial performance goals are provisional and must be validated with
load tests.

-   Establish baseline API latency before setting strict SLOs.
-   Track p50, p95, and p99 latency.
-   Measure database pool wait time and connection utilization.
-   Avoid loading model artifacts on every inference request.
-   Keep CPU-bound inference from blocking the event loop.
-   Use a bounded execution strategy for blocking or CPU-intensive work.
-   Avoid unbounded in-memory queues and task creation.

Potential first benchmark targets, subject to hardware and model choice:

-   Metadata API: p95 under 200 ms at modest local load.
-   Simple CPU inference: establish a model-specific baseline before
    setting a target.
-   Error rate: measure separately for client errors, platform errors,
    and dependency failures.

These are engineering targets, not guarantees.

## 5.3 Security

-   Secrets must not be committed to version control.
-   Production secrets should be injected through a secret manager or
    deployment environment.
-   Validate and constrain uploaded artifact types and sizes.
-   Do not execute arbitrary uploaded Python code.
-   Avoid logging sensitive inference payloads by default.
-   Apply authentication and authorization before exposing the platform
    beyond a trusted local environment.
-   Use TLS at deployment boundaries.
-   Apply least privilege to database and object-storage credentials.
-   Validate all external input.
-   Keep dependencies patched and scan images/packages.

## 5.4 Maintainability

-   Keep domain logic independent of frameworks and infrastructure.
-   Use explicit interfaces at meaningful boundaries.
-   Avoid unnecessary abstractions that do not protect a real boundary.
-   Enforce formatting, linting, and type checks.
-   Write tests around business rules and critical integration
    boundaries.
-   Document architectural decisions in ADRs.

## 5.5 Scalability

-   Begin with a modular monolith.
-   Make application instances stateless where practical.
-   Store durable state in PostgreSQL and object storage.
-   Keep model runtime state isolated behind an interface.
-   Size database pools based on process and replica counts.
-   Extract services only when independent scaling, deployment, fault
    isolation, or team ownership provides a measurable benefit.

------------------------------------------------------------------------

# 6. Architecture Principles

## 6.1 Architectural decision: modular monolith first

The initial deployment is one application with clearly separated domain
modules. This reduces operational complexity while preserving internal
boundaries.

A modular monolith is not a single unstructured codebase. Modules should
own their domain concepts, use cases, persistence interfaces, and public
contracts.

## 6.2 Clean Architecture and dependency direction

The dependency direction points inward:

1.  **Domain:** entities, value objects, domain services, domain rules,
    and ports.
2.  **Application:** use cases, orchestration, transaction boundaries,
    and application ports.
3.  **Infrastructure:** SQLAlchemy, PostgreSQL, object storage, cache,
    ML framework adapters, and telemetry exporters.
4.  **Presentation:** FastAPI routes, request/response schemas, and HTTP
    concerns.

The domain must not import FastAPI, SQLAlchemy, Pydantic Settings, Redis
clients, or concrete storage SDKs.

The application layer may depend on domain types and abstractions.
Infrastructure implements those abstractions. Presentation translates
HTTP requests into application calls.

## 6.3 DDD-inspired module boundaries

Potential initial modules:

-   `model_registry`: model identity and metadata.
-   `model_versions`: version lifecycle and artifact references.
-   `inference`: prediction orchestration and inference records.
-   `artifacts`: artifact storage and retrieval.
-   `deployments`: active version and deployment configuration (may
    initially remain inside model versions).
-   `observability`: instrumentation and operational metadata
    (cross-cutting, not necessarily a business domain).

Do not create all modules at once. Introduce each module when its first
use case is implemented.

## 6.4 Ports and adapters

Examples:

-   `ModelRepository` --- domain/application-facing persistence
    contract.
-   `ArtifactStore` --- contract for storing and retrieving model
    artifacts.
-   `ModelRuntime` --- contract for loading a model and executing
    predictions.
-   `UnitOfWork` --- contract for coordinating a transaction across
    repositories when needed.

Adapters may include:

-   SQLAlchemy model repository.
-   S3-compatible artifact store (SeaweedFS locally).
-   scikit-learn runtime adapter.
-   PyTorch runtime adapter.
-   OpenTelemetry instrumentation adapter.

## 6.5 Application factory and lifespan

`create_app()` constructs the FastAPI application and wires routers,
settings, middleware, and lifespan.

Lifespan owns long-lived process resources such as:

-   SQLAlchemy AsyncEngine.
-   Async session factory.
-   Redis client (when introduced).
-   Object-storage client (when introduced).
-   Model runtime manager (when introduced).
-   Telemetry providers/exporters (when introduced).

Do not create a new engine or connection pool for every request.

## 6.6 Initial repository structure

This is a target structure to evolve toward, not a requirement to create
every file immediately:

``` text
atlas-ml-platform/
├── pyproject.toml
├── uv.lock
├── README.md
├── .env
├── .env.example
├── .gitignore
├── docker-compose.yml
├── migrations/
├── docs/
│   ├── architecture/
│   │   └── adr/
│   ├── api/
│   └── operations/
├── src/
│   └── atlas_ml_platform/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── router.py
│       │   ├── dependencies.py
│       │   └── middleware/
│       ├── core/
│       │   ├── application.py
│       │   ├── lifespan.py
│       │   ├── logging.py
│       │   └── errors.py
│       ├── modules/
│       │   ├── model_registry/
│       │   │   ├── domain/
│       │   │   ├── application/
│       │   │   ├── infrastructure/
│       │   │   └── presentation/
│       │   ├── model_versions/
│       │   ├── artifacts/
│       │   └── inference/
│       ├── infrastructure/
│       │   ├── database/
│       │   │   ├── base.py
│       │   │   ├── engine.py
│       │   │   ├── session.py
│       │   │   └── unit_of_work.py
│       │   ├── object_storage/
│       │   ├── cache/
│       │   └── telemetry/
│       └── shared/
│           ├── domain/
│           └── application/
└── tests/
    ├── unit/
    ├── integration/
    ├── contract/
    └── e2e/
```

`shared/` must remain small. Do not move code there merely because
multiple modules import it. Shared abstractions should represent
genuinely cross-module concepts.

------------------------------------------------------------------------

# 7. Technology Stack

## 7.1 Core backend

  Concern             Initial choice         Rationale
  ------------------- ---------------------- --------------------------------------------
  Language            Python 3.12+           Mature ML ecosystem and modern typing
  Package manager     uv                     Fast dependency and environment management
  API framework       FastAPI                Typed API and ASGI support
  ASGI server         Uvicorn                Application process server
  Validation          Pydantic v2            Request and configuration validation
  Settings            pydantic-settings      Environment-based configuration
  ORM                 SQLAlchemy 2.x async   Explicit async database access
  PostgreSQL driver   asyncpg                Async PostgreSQL connectivity
  Database            PostgreSQL 17          Durable relational metadata
  Migrations          Alembic                Versioned schema evolution

## 7.2 Development quality

-   pytest
-   pytest-asyncio
-   HTTPX / supported ASGI test client
-   Ruff
-   mypy
-   pre-commit (optional)
-   Docker Compose

Pin compatible dependency ranges and commit `uv.lock`.

## 7.3 ML and artifact ecosystem

Planned options:

-   scikit-learn for the first demonstrator model.
-   PyTorch for a later deep-learning runtime.
-   MLflow for experiment/model lifecycle integration if useful.
-   SeaweedFS locally and S3-compatible storage in production.
-   Redis only when caching, coordination, or a measured use case
    requires it.

## 7.4 Observability ecosystem

-   OpenTelemetry SDK and instrumentation.
-   Prometheus for metrics.
-   Grafana for dashboards.
-   Tempo for traces.
-   Loki for log aggregation (optional).
-   Structured JSON application logs.

## 7.5 Load and performance testing

-   k6 or Locust.
-   PostgreSQL query analysis and `EXPLAIN ANALYZE`.
-   Application profiling where bottlenecks are identified.

------------------------------------------------------------------------

# 8. Configuration and Environment Strategy

## 8.1 Configuration sources

-   `.env`: local development configuration; never commit.
-   `.env.example`: safe template; commit.
-   Environment variables: override `.env`.
-   Production: deployment environment or secret manager; do not depend
    on a checked-in `.env`.

## 8.2 Initial local `.env` example

Use local-only values and keep credentials consistent across Compose and
the application:

``` dotenv
APP_NAME=Atlas ML Platform
APP_ENV=development
DEBUG=true
LOG_LEVEL=DEBUG

POSTGRES_USER=atlas
POSTGRES_PASSWORD=atlas_dev_password
POSTGRES_DB=atlas_dev

DATABASE_URL=postgresql+asyncpg://atlas:atlas_dev_password@localhost:5432/atlas_dev
DATABASE_ECHO=false

DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
```

The password above is a local development placeholder. Use a generated
secret if the environment is shared or exposed.

## 8.3 `.env.example`

``` dotenv
APP_NAME=Atlas ML Platform
APP_ENV=development
DEBUG=false
LOG_LEVEL=INFO

POSTGRES_USER=atlas
POSTGRES_PASSWORD=CHANGE_ME
POSTGRES_DB=atlas_dev

DATABASE_URL=postgresql+asyncpg://atlas:CHANGE_ME@localhost:5432/atlas_dev
DATABASE_ECHO=false

DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
```

## 8.4 Settings design

The Pydantic Settings model should:

-   Require `DATABASE_URL` rather than silently inventing a database
    target.
-   Validate `APP_ENV` against known values.
-   Use typed values for pool configuration.
-   Keep `DATABASE_ECHO` disabled by default.
-   Ignore unrelated environment keys if Compose and the app share one
    `.env`.
-   Avoid exposing secrets in logs or exception messages.

A cached `get_settings()` function is acceptable for process-level
settings. Tests should instantiate settings with environment-file
loading disabled when isolation is required.

## 8.5 Important Docker Compose distinction

Compose uses the root `.env` for variable interpolation. The Compose
`environment:` section passes selected values into the container. An
`env_file:` declaration is a separate mechanism for injecting variables
into a container.

The application running on the host uses `localhost:5432`. An
application running inside the Compose network should use the PostgreSQL
service name, e.g. `postgres:5432`, not `localhost`.

PostgreSQL initialization variables such as `POSTGRES_USER`,
`POSTGRES_PASSWORD`, and `POSTGRES_DB` are applied when the data
directory is initialized. Changing them later does not automatically
alter an existing database volume.

------------------------------------------------------------------------

# 9. Database Design and Persistence Strategy

## 9.1 Database topology

Use one PostgreSQL server/container initially, with separate databases:

-   `atlas_dev`: persistent local development data.
-   `atlas_test`: isolated test data that can be reset.

Do not let automated tests connect to `atlas_dev`.

A single PostgreSQL database is sufficient for the initial modular
monolith. Domain modules may own separate tables and repository
boundaries without requiring separate database servers.

## 9.2 Persistence responsibilities

PostgreSQL stores:

-   Model metadata.
-   Model version metadata.
-   Artifact references and checksums.
-   Deployment/active-version state.
-   Inference metadata where retention requirements permit.
-   Audit and operational records as appropriate.

Object storage stores:

-   Serialized model artifacts.
-   Model weights.
-   Large files and binary assets.
-   Optional evaluation outputs or supporting files.

Do not store large `.joblib`, `.pkl`, `.pt`, or similar model binaries
as ordinary relational columns.

## 9.3 SQLAlchemy engine

Create one `AsyncEngine` per application process, during lifespan.

Initial tunables:

-   `pool_size=5`
-   `max_overflow=10`
-   `pool_timeout=30`
-   `pool_recycle=1800`
-   `pool_pre_ping=True`

`pool_pre_ping` should generally remain enabled as a safe operational
default. Pool sizing is environment-dependent and must be considered
across all worker processes and replicas.

For example, `pool_size=5` plus `max_overflow=10` permits up to 15
connections per process. Four worker processes could therefore create up
to 60 connections, before considering other services or administrative
connections.

`pool_recycle` is evaluated when a connection is checked out; it is not
a timer that forcibly closes a connection currently in use.

## 9.4 Session strategy

-   Use `async_sessionmaker`.
-   Use one `AsyncSession` per request or unit of work.
-   Do not share an `AsyncSession` concurrently across tasks.
-   Close sessions reliably.
-   Do not silently auto-commit in a generic dependency.
-   Define transaction ownership in application use cases or a Unit of
    Work abstraction.

A request-scoped session dependency manages session lifetime, not
necessarily transaction policy.

## 9.5 Migrations

Use Alembic for schema changes.

Rules:

-   Schema changes must be represented by migration files.
-   Do not rely on `Base.metadata.create_all()` as the production
    migration strategy.
-   Test both upgrade and, where practical, downgrade behavior.
-   Keep migrations reviewable and deterministic.
-   Avoid destructive migrations without explicit data migration and
    rollback planning.

------------------------------------------------------------------------

# 10. API Design Baseline

The following endpoints are an initial direction. Exact schemas and
status codes should be finalized when each use case is implemented.

## 10.1 Health

-   `GET /api/v1/health` --- process liveness.
-   `GET /api/v1/health/ready` --- readiness, including critical
    dependency checks.

The early `/health/database` diagnostic endpoint has been removed;
readiness now covers both PostgreSQL and S3 checks.

Liveness should not fail merely because PostgreSQL is unavailable.
Readiness should reflect whether the service can safely accept work.

## 10.2 Models

-   `POST /api/v1/models`
-   `GET /api/v1/models`
-   `GET /api/v1/models/{model_id}`
-   `PATCH /api/v1/models/{model_id}`
-   `POST /api/v1/models/{model_id}/archive`

## 10.3 Versions

-   `POST /api/v1/models/{model_id}/versions`
-   `GET /api/v1/models/{model_id}/versions`
-   `GET /api/v1/models/{model_id}/versions/{version_id}`
-   `POST /api/v1/models/{model_id}/versions/{version_id}/activate`

## 10.4 Inference

-   `POST /api/v1/models/{model_id}/predict`
-   Optionally support an explicit version path or request field when
    version pinning is required.

## 10.5 API conventions

-   Use consistent pagination.
-   Use stable identifiers.
-   Validate payloads at the boundary.
-   Keep internal ORM objects out of public responses.
-   Use explicit response schemas.
-   Return appropriate HTTP status codes.
-   Avoid leaking stack traces or infrastructure details.
-   Document idempotency expectations for operations that may be
    retried.

------------------------------------------------------------------------

# 11. Testing Strategy

## 11.1 Unit tests

Test domain and application behavior without PostgreSQL, HTTP servers,
or external storage.

Examples:

-   Model name validation.
-   Version uniqueness rules.
-   Allowed lifecycle transitions.
-   Activation constraints.
-   Inference request validation.
-   Error mapping and use-case behavior.

## 11.2 Integration tests

Test adapters and infrastructure against real dependencies where
practical.

Examples:

-   SQLAlchemy repository against `atlas_test`.
-   Alembic migrations against a fresh test database.
-   Object storage adapter against SeaweedFS.
-   API database dependency and transaction behavior.

## 11.3 API tests

Use an ASGI test client or supported test transport.

-   Test success and failure responses.
-   Override dependencies deliberately.
-   Exercise lifespan when validating startup/shutdown behavior.
-   Do not assume a test client automatically invokes lifespan unless
    used in the supported context-manager pattern.

## 11.4 End-to-end tests

Run the complete stack and test a user journey:

1.  Register model.
2.  Create version.
3.  Upload/register artifact.
4.  Activate version.
5.  Send inference request.
6.  Inspect response and operational metadata.

## 11.5 Test database safety

Tests must never silently use `atlas_dev`.

Recommended safeguards:

-   Separate `TEST_DATABASE_URL`.
-   Require an explicit testing environment.
-   Assert the target database name is `atlas_test` before destructive
    fixture setup.
-   Use isolated schemas or disposable databases where appropriate.
-   Make cleanup explicit.
-   Fail closed if the target database cannot be verified.

## 11.6 Quality gates

Before merging or completing a milestone:

``` bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Adjust mypy scope and configuration as the project evolves. Add
migration checks and integration-test commands when those capabilities
exist.

------------------------------------------------------------------------

# 12. Observability and Production Operations

## 12.1 Three pillars

### Logs

Explain discrete events. Use structured logs with timestamp, severity,
service name, environment, request ID, and trace ID where available.

### Metrics

Describe aggregate behavior over time. Start with:

-   Request count.
-   Request duration histogram.
-   HTTP error count.
-   In-flight requests.
-   Database pool utilization and checkout wait.
-   Database query duration.
-   Inference count and duration.
-   Model load duration and failures.
-   Process CPU and memory.

Avoid high-cardinality labels such as raw request IDs, user IDs, or
arbitrary input values in Prometheus labels.

### Traces

Show the path of an operation across boundaries. A useful inference
trace may contain:

-   HTTP request.
-   Application use case.
-   Model/version lookup.
-   Artifact retrieval.
-   Model loading (when applicable).
-   Prediction execution.
-   Database writes.

## 12.2 OpenTelemetry

Instrument progressively:

1.  Configure service resource attributes.
2.  Instrument FastAPI/ASGI.
3.  Instrument SQLAlchemy.
4.  Propagate trace context.
5.  Export traces to a local collector or Tempo.
6.  Correlate trace IDs with logs.
7.  Add custom spans around artifact retrieval and inference.

Do not add custom spans for every trivial function. Instrument
meaningful boundaries.

## 12.3 Prometheus and Grafana

Expose metrics through a Prometheus scrape endpoint or collector
pipeline. Build dashboards around service health and user-visible
behavior rather than only infrastructure internals.

Initial dashboard panels:

-   Request rate.
-   p50/p95/p99 latency.
-   HTTP 4xx and 5xx rates.
-   Inference throughput and latency.
-   Model load duration.
-   Database connection pool state.
-   CPU and memory.
-   Dependency failures.

## 12.4 Graceful shutdown

The service should:

1.  Stop accepting new work.
2.  Allow in-flight requests to finish within a bounded grace period.
3.  Stop or cancel application-managed background tasks safely.
4.  Flush telemetry exporters where supported.
5.  Close Redis/object-storage clients if present.
6.  Dispose the SQLAlchemy engine.
7.  Exit within the configured server/container shutdown timeout.

Do not create unmanaged background tasks. Track them, define
cancellation behavior, and await their completion.

## 12.5 Health semantics

-   **Liveness:** Is the process alive and not irrecoverably stuck?
-   **Readiness:** Can this instance accept the work it is responsible
    for?
-   **Startup probe (if orchestrated):** Has initialization completed?

A database outage may make readiness fail while liveness remains
healthy. This prevents an orchestrator from repeatedly restarting a
process that is otherwise functioning and could recover when the
dependency returns.

------------------------------------------------------------------------

# Learning-First Project Charter

## The real goal: become able to build this kind of system independently

The main outcome of Atlas is **the learner's engineering capability**, not the amount of code produced. The platform is a practical learning environment: every feature exists both to deliver product functionality and to teach an important engineering concept.

By the end of the project, the learner should be able to:
- Explain the architecture and the reasons behind its boundaries.
- Follow a request from the HTTP route through application logic and infrastructure to the database or model runtime.
- Understand resource ownership: who creates, uses, and closes engines, sessions, clients, tasks, and exporters.
- Implement a feature in small steps without blindly copying a complete solution.
- Write tests, interpret failures, inspect runtime behavior, and debug issues systematically.
- Explain trade-offs and identify when a design should change.
- Transfer the concepts to a different production backend or ML system.

A working endpoint is evidence that code runs. It is **not by itself evidence that the concept has been learned**.

## What it means to truly understand a topic

For each important topic, aim to reach these five levels:

1. **Describe:** Explain what it is in plain language.
2. **Explain why:** Identify the problem it solves and why Atlas needs it.
3. **Trace:** Follow its runtime behavior, control flow, data flow, and lifecycle.
4. **Implement and verify:** Make a small change, run it, and verify the result with a test, command, log, query, or observable behavior.
5. **Reason about trade-offs:** Explain alternatives, failure modes, operational costs, and when the current approach would no longer be appropriate.

The AI agent should help the learner reach these levels. It should occasionally ask the learner to predict what a command or code path will do, or ask which layer should own a rule. These questions should be contextual and supportive, not turn every conversation into an exam.

## Required learning loop for every milestone

Milestones must be implemented as a sequence of small learning steps, not as one large code-generation task.

1. **Inspect:** Read the current repository and establish what is actually implemented.
2. **Orient:** State the exact sub-step and why it comes next.
3. **Teach:** Explain the concept, problem, mental model, and relevant vocabulary before implementation.
4. **Predict:** Invite the learner to reason about expected behavior where useful.
5. **Design:** Choose the smallest implementation that teaches the concept and advances Atlas.
6. **Implement:** Change a small, coherent set of files. Do not generate the entire milestone at once.
7. **Run:** Execute the application or focused command and inspect the actual output.
8. **Test and debug:** Add or run tests. Diagnose failures rather than hiding them with broad rewrites.
9. **Trace and explain:** Walk through the runtime flow, important code, resource ownership, and failure behavior.
10. **Consolidate:** Summarize what was learned, what decisions were made, and what remains unclear.
11. **Exit check:** Confirm the learner can explain the essential idea and make a small modification independently.

A milestone may take multiple sessions. That is expected. The pace is determined by understanding, not by how quickly the checklist is completed.

## How the AI agent should teach

For every new technology or architectural pattern, explain:

- **What:** A precise, accessible definition.
- **Why:** The concrete problem it solves in Atlas.
- **Where:** Which layer or module owns it.
- **How:** The runtime sequence and data/control flow.
- **Failure modes:** What can go wrong and how it appears.
- **Alternatives:** Relevant options and why one is chosen now.
- **Verification:** How to prove that it works.

When showing code:
- Explain the important lines and their responsibility.
- Explain how the code is reached at runtime.
- Avoid dumping many files before the learner understands the design.
- Avoid over-explaining syntax the learner already knows; focus on new concepts and consequential decisions.
- Do not move to the next sub-step until the learner has had a chance to ask questions.

For example, when implementing a database-backed API, trace the full path:

`HTTP request -> router -> dependency resolution -> application use case -> repository -> SQLAlchemy session -> PostgreSQL -> response`

Explain which component creates each resource, which component uses it, and which component is responsible for cleanup.

## A milestone is complete only when both outcomes exist

**Product outcome**
- The intended behavior is implemented.
- Relevant tests or verification steps pass.
- The feature works in the running application.
- Documentation is updated where needed.

**Learning outcome**
- The learner can explain what was built and why.
- The learner can trace the execution flow.
- The learner understands the main failure modes.
- The learner can make a small change or diagnose a simple issue without the agent doing all the reasoning.
- Important trade-offs are understood and recorded.

Do not mark a milestone complete based only on generated code or a passing happy-path request.

---

# 13. Delivery Roadmap and Milestones

Milestones are ordered as a step-by-step implementation curriculum.
Their order is intentional: each milestone introduces concepts that the
next milestone relies on. Do not treat the roadmap as a checklist to rush
through.

For each milestone, split the work into small sub-steps. Explain the
concept first, implement one coherent slice, run it, inspect the output,
test it, and explain what happened. Pause at natural checkpoints so the
learner can ask questions before continuing. A milestone can span multiple
conversations or sessions; that is normal and encouraged.

Each milestone should end with a demonstrable result, tests or verification
evidence, a short engineering note explaining decisions and trade-offs,
and a learning checkpoint confirming what the learner can now explain or
do independently.

## Milestone 0 --- Project bootstrap and developer workflow

**Objective:** Establish a reproducible Python project.

Tasks: - Initialize package with `uv`. - Configure `pyproject.toml`. -
Use `src/` layout. - Add FastAPI and Uvicorn. - Add Ruff, mypy, pytest,
and test configuration. - Add `.gitignore`, README, `.env.example`. -
Confirm package imports and application startup.

Deliverables: - Reproducible dependency lock. - Minimal runnable FastAPI
app. - Documented local commands.

Acceptance criteria: - Fresh environment can install dependencies. - App
starts through Uvicorn. - Basic test passes. - No secrets are committed.

Concepts to learn: - Python packaging. - `src` layout. - ASGI. -
Uvicorn. - Dependency locking.

## Milestone 1 --- Application architecture and lifecycle

**Objective:** Introduce a clean application composition root.

Tasks: - Implement `create_app()`. - Add API router composition. - Add
`/api/v1/health`. - Add lifespan context manager. - Store app-level
resources in `app.state` only where appropriate. - Add startup/shutdown
tests. - Understand Uvicorn import-string and factory modes.

Deliverables: - Application factory. - Router structure. - Lifespan
implementation. - Tests for app creation and lifecycle.

Acceptance criteria: - App can be created with injected settings. -
Lifespan startup and shutdown run predictably. - Routes are mounted
under `/api/v1`. - No infrastructure resource is created at module
import time.

Concepts to learn: - Application Factory. - Dependency injection. - ASGI
lifespan. - Process-level resources. - Graceful shutdown fundamentals.

## Milestone 2 --- Configuration management

**Objective:** Make configuration explicit, typed, and
environment-aware.

Tasks: - Implement Pydantic Settings. - Define `APP_ENV`, `DEBUG`,
`LOG_LEVEL`, and required `DATABASE_URL`. - Add database echo and pool
settings. - Separate `.env` from `.env.example`. - Confirm environment
variables override `.env`. - Add settings tests with environment-file
loading disabled. - Avoid logging secrets.

Deliverables: - `config.py`. - Local `.env`. - Safe `.env.example`. -
Configuration tests.

Acceptance criteria: - Missing required configuration fails clearly. -
Invalid environment values fail validation. - Tests do not accidentally
inherit local `.env`. - No credentials are committed.

Concepts to learn: - Environment configuration. - Twelve-factor
configuration principles. - Secret handling. - Settings validation and
caching.

## Milestone 3 --- Local PostgreSQL infrastructure

**Objective:** Run a persistent local database with a separate test
database.

Tasks: - Add PostgreSQL 17 Alpine to Compose. - Add named volume. - Bind
published port to localhost. - Add health check. - Configure consistent
Compose and app credentials. - Start PostgreSQL and inspect logs. -
Create `atlas_test`. - Verify connection with `psql`. - Document volume
persistence and destructive operations.

Deliverables: - `docker-compose.yml`. - Working PostgreSQL container. -
`atlas_dev` and `atlas_test`. - Database setup documentation.

Acceptance criteria: - Container reports healthy. - App credentials
match database initialization. - Development data persists across normal
container restarts. - Test database is separate. - Developers understand
that `down -v` deletes the volume.

Concepts to learn: - Docker Compose. - Container networking. -
Environment interpolation. - Named volumes. - PostgreSQL
initialization. - Health checks.

## Milestone 4 --- SQLAlchemy async infrastructure

**Objective:** Establish safe database resource management.

Tasks: - Implement async engine factory. - Implement async session
factory. - Add request-scoped session dependency. - Create engine and
session factory in lifespan. - Dispose engine on shutdown. - Add
database connectivity probe. - Add `/health/database` as an early
diagnostic endpoint (superseded by `/health/ready`). - Test startup
failure and cleanup behavior. -
Verify the app uses the intended database URL.

Deliverables: - `infrastructure/database/engine.py`. -
`infrastructure/database/session.py`. - Updated lifespan. - Database
health endpoint. - Integration test for connectivity.

Acceptance criteria: - One engine is created per application process. -
Sessions are scoped to requests/use cases. - Sessions close after use. -
Engine is disposed on shutdown. - Connection failures are reported
clearly. - No test can accidentally use `atlas_dev`.

Concepts to learn: - Engine vs connection vs session. - AsyncSession
lifecycle. - Connection pooling. - Pool sizing across workers. -
`pool_pre_ping` and `pool_recycle`. - Async resource cleanup.

## Milestone 5 --- ORM foundation and Alembic migrations

**Objective:** Introduce schema evolution without coupling domain
entities to ORM models.

Tasks: - Define SQLAlchemy declarative Base and metadata. - Configure
Alembic for the project layout. - Configure async migration connectivity
if desired. - Create first migration. - Add a minimal persistence
model. - Run upgrade and inspect schema. - Test migration against a
fresh `atlas_test`. - Document migration workflow.

Deliverables: - ORM Base. - Alembic configuration. - Initial
migration. - Migration commands in README.

Acceptance criteria: - Fresh database can be migrated from zero. -
Migration history is committed. - ORM metadata is discoverable by
Alembic. - Production schema changes do not rely on `create_all()`.

Concepts to learn: - ORM mapping. - Declarative metadata. - Alembic
autogenerate and review. - Schema versioning. - Migration safety.

## Milestone 6 --- First vertical slice: model registry

**Objective:** Implement one complete feature through all architecture
layers.

Tasks: - Define Model domain entity and value objects. - Define
repository port. - Define create/get/list use cases. - Implement
SQLAlchemy repository adapter. - Define Pydantic request/response
schemas. - Implement FastAPI routes. - Add unit and integration tests. -
Add pagination and error mapping.

Deliverables: - Working model registration API. - Persistence adapter. -
Domain and application tests. - API documentation.

Acceptance criteria: - Client can create, retrieve, and list models. -
Domain rules are tested without database access. - Repository
integration tests use `atlas_test`. - HTTP schemas do not expose ORM
internals.

Concepts to learn: - Domain entities. - Repository pattern. - Use
cases. - Ports and adapters. - Vertical-slice development. - DTOs and
API contracts.

## Milestone 7 --- Model versioning and lifecycle

**Objective:** Manage multiple immutable model versions and their
lifecycle.

Tasks: - Define ModelVersion domain concept. - Decide version identifier
and uniqueness rules. - Define lifecycle states and valid transitions. -
Persist version metadata. - Add create/list/get version use cases. -
Implement activation rules. - Ensure active-version updates are
transactionally consistent. - Add concurrency and conflict tests.

Deliverables: - Model version APIs. - Version persistence. - Lifecycle
rules. - Activation behavior.

Acceptance criteria: - A model can have multiple versions. - Duplicate
version identifiers are rejected. - Invalid lifecycle transitions are
rejected. - Activation cannot point to a nonexistent or ineligible
version. - Concurrent activation behavior is defined.

Concepts to learn: - Aggregate boundaries. - Domain invariants. -
Transactions. - Optimistic concurrency where needed. - State machines.

## Milestone 8 --- Object storage and artifact management

**Objective:** Store model binaries outside PostgreSQL.

Tasks: - Add SeaweedFS to local Compose. - Define ArtifactStore port. -
Implement S3-compatible adapter. - Add upload and download flows. -
Persist artifact URI, checksum, size, and format. - Verify checksum after
upload/download. - Add size/type constraints. - Test storage adapter
against local SeaweedFS.

Deliverables: - Object-storage service. - Artifact metadata
persistence. - Artifact API or upload workflow.

Acceptance criteria: - Artifact bytes are stored in object storage. -
PostgreSQL stores only metadata and references. - Artifact retrieval
works. - Integrity checks detect corrupted content. - Credentials are
not hardcoded. - A model version cannot reference an unregistered
artifact URI.

Concepts to learn: - Object storage. - S3-compatible APIs. - Presigned
URLs (if selected). - Checksums. - Storage abstraction. - Upload
security.

## Milestone 9 --- First ML runtime and inference vertical slice

**Objective:** Serve one real model end to end.

Tasks: - Choose a small deterministic scikit-learn model and dataset. -
Define ModelRuntime port. - Implement model loading and prediction
adapter. - Define inference request/response contracts. - Resolve active
model version. - Load artifact and cache the loaded runtime safely. -
Add timeouts and error mapping. - Run inference through the API. - Add
integration and end-to-end tests.

Deliverables: - Working prediction endpoint. - One example model
artifact. - Runtime adapter. - Inference documentation.

Acceptance criteria: - A registered and activated model can serve
predictions. - Input validation is deterministic. - Model loading errors
are distinguishable from prediction errors. - Artifact is not
unnecessarily loaded for every request. - Inference returns a request
ID. - CPU-bound execution does not block the event loop.

Concepts to learn: - Model serialization. - Runtime abstraction. - Model
loading and caching. - CPU-bound vs I/O-bound work. - Thread/process
execution strategies. - Inference contracts.

Security note: Never deserialize untrusted pickle/joblib artifacts or
execute arbitrary model code from an untrusted source. Treat artifacts
as executable-risk inputs and define a trusted-artifact policy. A
development-only auto-trust mode may exist outside production; production
must use an explicit allowlist or approval workflow and reject auto-trust
at startup.

## Milestone 10 --- Structured logging and error handling

**Objective:** Make failures diagnosable.

Tasks: - Configure standard structured logging. - Add consistent
exception handling. - Add request ID middleware or equivalent. - Include
safe contextual fields. - Avoid logging secrets and raw sensitive
payloads. - Add tests for error responses. - Document log fields.

Deliverables: - Logging configuration. - Error response contract. -
Request correlation. - Operational logging guide.

Acceptance criteria: - Errors are logged once at the appropriate
boundary. - API clients receive safe error responses. - Logs contain
enough context to locate a request. - Sensitive values are redacted or
omitted.

Concepts to learn: - Structured logging. - Logging boundaries. -
Correlation IDs. - Error taxonomy. - Exception translation.

## Milestone 11 --- OpenTelemetry tracing

**Objective:** Trace requests through application and infrastructure
boundaries.

Tasks: - Configure service resource attributes. - Instrument FastAPI. -
Instrument SQLAlchemy. - Configure trace exporter. - Run a local OTLP
backend (Jaeger locally; Collector/Tempo in production). - Add custom
spans for model lookup, artifact retrieval, and inference. - Correlate
traces with logs. - Verify trace context propagation.

Deliverables: - Distributed trace pipeline. - Trace examples. -
Instrumentation configuration.

Acceptance criteria: - An API request produces a trace. - Database
operations appear as child spans. - Inference stages can be inspected. -
Trace IDs can be correlated with logs.

Concepts to learn: - Trace/span/context. - Parent-child relationships. -
Context propagation. - Sampling. - Instrumentation vs application logic.

## Milestone 12 --- Prometheus metrics and Grafana dashboards

**Objective:** Measure system behavior quantitatively.

Tasks: - Expose or export application metrics. - Add HTTP request count
and duration. - Add inference count and duration. - Add model load
metrics. - Add database pool metrics where practical. - Configure
Prometheus scraping. - Create Grafana dashboards. - Review metric
cardinality.

Deliverables: - Prometheus configuration. - Grafana dashboards. - Metric
definitions.

Acceptance criteria: - Metrics are scraped successfully. - Dashboard
shows request rate, latency, and errors. - Inference metrics can be
filtered by bounded labels. - No unbounded identifiers are used as
metric labels.

Concepts to learn: - Counters, gauges, histograms. - RED and USE
methods. - Cardinality. - Histograms and percentiles. - Dashboard
design.

## Milestone 13 --- Reliability and graceful shutdown

**Objective:** Ensure predictable behavior under shutdown and dependency
failures.

Tasks: - Separate liveness and readiness. - Add startup/readiness
semantics. - Configure server and container shutdown grace periods. -
Track and stop background tasks. - Flush telemetry. - Close all
long-lived clients. - Dispose database engine. - Test shutdown with
in-flight requests. - Define timeout and retry policy for external
dependencies.

Deliverables: - Reliability behavior. - Shutdown tests. - Operational
runbook.

Acceptance criteria: - New work is not accepted after shutdown begins. -
In-flight work has a bounded completion window. - Background tasks are
not abandoned silently. - Connections and exporters are closed. -
Readiness accurately reflects dependency health.

Concepts to learn: - Graceful termination. - Cancellation. - Timeouts. -
Retry budgets. - Backpressure. - Failure isolation.

## Milestone 14 --- Performance testing and capacity planning

**Objective:** Measure the system and make evidence-based improvements.

Tasks: - Define representative request workloads. - Add k6 or Locust
scenarios. - Establish baseline latency and throughput. - Measure
database pool saturation. - Measure model loading and inference
latency. - Profile CPU and memory. - Identify bottlenecks before
optimizing. - Document capacity assumptions.

Deliverables: - Load-test scripts. - Baseline report. - Capacity
model. - Prioritized optimization list.

Acceptance criteria: - Tests are repeatable. - p50/p95/p99 are
reported. - Bottlenecks are supported by measurements. - Pool sizing
accounts for worker and replica counts. - No optimization is accepted
without evidence.

Concepts to learn: - Load vs stress vs soak tests. - Throughput and
latency. - Little's Law. - Queueing and saturation. - Connection
budgets. - Profiling.

## Milestone 15 --- Deployment and production hardening

**Objective:** Package and operate the service in a production-like
environment.

Tasks: - Build a multi-stage Docker image. - Run as a non-root user. -
Configure health checks. - Separate build-time and runtime
configuration. - Add resource limits where appropriate. - Configure
migrations as a controlled deployment step. - Add authentication and
authorization. - Configure TLS at the deployment boundary. - Define
backup and restore for PostgreSQL and object storage. - Document
rollback strategy. - Add CI pipeline.

Deliverables: - Production-oriented Dockerfile. - Deployment
configuration. - CI workflow. - Operations and recovery documentation.

Acceptance criteria: - Image is reproducible and minimal enough for its
purpose. - Secrets are injected securely. - Migrations are controlled. -
Health checks work. - Backup and restore procedure is tested. -
Deployment and rollback steps are documented.

Concepts to learn: - Container hardening. - CI/CD. - Deployment
strategies. - Secrets management. - Backup/restore. - Operational
readiness.

## Milestone 16 --- Optional advanced extensions

Only start these after the core platform works and has measurable
limitations.

Potential extensions: - Redis caching for model metadata or runtime
coordination. - Background inference jobs using a task queue. - Batch
inference. - Multi-tenancy and RBAC. - Model evaluation reports. - Drift
monitoring. - Canary or shadow deployments. - A/B testing and traffic
splitting. - GPU inference workers. - MLflow integration. - Kubernetes
deployment. - Service extraction when justified by independent scaling
or ownership needs.

------------------------------------------------------------------------

# 14. Milestone Dependency Map

``` text
M0 Bootstrap
  |
M1 App factory + lifecycle
  |
M2 Configuration
  |
M3 PostgreSQL infrastructure
  |
M4 SQLAlchemy async
  |
M5 ORM + Alembic
  |
M6 Model registry
  |
M7 Model versions
  |
M8 Artifact storage
  |
M9 Inference runtime
  |
M10 Structured logging
  |
M11 OpenTelemetry
  |
M12 Prometheus + Grafana
  |
M13 Reliability + graceful shutdown
  |
M14 Performance + capacity
  |
M15 Deployment hardening
  |
M16 Optional extensions
```

Some cross-cutting work can overlap. For example, structured logs should
be introduced early enough to help debug infrastructure, while full
OpenTelemetry instrumentation can wait until the core request flow
exists.

------------------------------------------------------------------------

## Learning-first collaboration rules

The agent is a technical mentor and pair-programming partner, not an
autonomous code generator whose output the learner is expected to accept
blindly.

For every meaningful implementation step, the agent must:
1. Inspect the current code before editing.
2. Explain the concept and the reason for the change.
3. Identify the exact files that will change.
4. Implement only the agreed, small scope.
5. Run focused verification and report the actual output.
6. Explain the runtime flow and important design decisions.
7. State what the learner should now understand.
8. Offer one logical next step and wait for the learner to continue.

Do not generate all milestone code at once. Do not add infrastructure just
because it is fashionable. Do not introduce abstractions before a concrete
use case demonstrates their value. Do not claim that the learner
understands a topic merely because the code runs. When a failure occurs,
use it to teach debugging and diagnosis instead of replacing large parts
of the implementation without explanation.

# 15. Engineering Workflow and Collaboration with an AI Agent

This section is intended to help an AI coding agent work on the
repository without losing architectural context.

## 16.1 Working mode

Use **Learning by Building**.

The agent should not simply generate a large codebase. It should:

1.  Inspect the current repository before proposing edits.
2.  Identify the current milestone and actual implementation state.
3.  Explain the concept and the reason for the design.
4.  Propose a small, coherent implementation step.
5.  Make changes only within the agreed scope.
6.  Run relevant tests, lint, type checks, or validation commands.
7.  Report exactly what changed and what was verified.
8.  Explain remaining risks and the next logical step.

## 16.2 Do not assume the PRD describes the current code

This document describes intended direction, not proof that every
component exists.

The agent must inspect files and command output before claiming that a
feature is implemented. If the repository differs from this document,
report the discrepancy and recommend whether to update the
implementation or the PRD.

## 16.3 Response format for implementation sessions

For each meaningful engineering step, use:

### A. Current state

What exists now? What is missing?

### B. Concept

Explain the relevant technology or architecture.

### C. Design decision

Explain the recommended approach and alternatives worth considering.

### D. Implementation

Show the smallest useful code changes, with file paths.

### E. Verification

Provide commands and expected results. Do not claim commands passed
unless actually run.

### F. Engineering notes

Explain trade-offs, failure modes, security considerations, and
production implications.

### G. Next step

Identify one logical next task. Do not jump multiple milestones without
agreement.

## 16.4 Coding standards

-   Prefer clear, typed Python.
-   Use `async` only when the operation and dependency stack are
    genuinely asynchronous.
-   Keep I/O at infrastructure boundaries.
-   Keep domain rules framework-independent.
-   Use dependency injection at composition boundaries.
-   Avoid global mutable state.
-   Avoid import-time network connections or database engine creation.
-   Avoid broad exception swallowing.
-   Avoid generic abstractions without a real use case.
-   Use explicit timeouts for network operations.
-   Make resource ownership and cleanup obvious.
-   Use UTC-aware timestamps for persisted event times.
-   Keep API DTOs separate from ORM models and domain entities.
-   Avoid premature microservices and premature distributed
    infrastructure.

## 16.5 Change management

For each milestone:

-   Keep changes small enough to review.
-   Preserve working behavior unless a migration is intentional.
-   Add or update tests with behavior changes.
-   Update README and architecture docs when commands or decisions
    change.
-   Record significant decisions as Architecture Decision Records
    (ADRs).
-   Do not introduce a new dependency without explaining its purpose and
    maintenance cost.
-   Do not silently change database volumes, credentials, or migration
    history.
-   Clearly mark destructive commands.

## 16.6 AI agent safety rules

-   Never print `.env` secrets into chat or logs.
-   Never run destructive database or volume commands without explaining
    their impact and receiving confirmation.
-   Never run migrations against development or production databases
    without verifying the target.
-   Never assume a command succeeded; inspect its output.
-   Never fabricate test results, performance numbers, or endpoint
    responses.
-   Never commit secrets, private keys, tokens, or real customer data.
-   Treat model artifacts and uploaded files as untrusted inputs.
-   Ask before making broad architectural changes or introducing a new
    infrastructure service.

------------------------------------------------------------------------

# 17. Current Project State (Baseline at Document Creation)

This section captures the known state from the planning and
implementation discussion. It must be updated as work progresses.

## 16.1 Decisions already made

-   Project name: Atlas ML Platform.
-   Learning approach: Learning by Building.
-   Initial architecture: modular monolith.
-   Architectural principles: Clean Architecture, DDD-inspired modules,
    ports and adapters.
-   Backend language: Python.
-   API framework: FastAPI.
-   Server: Uvicorn.
-   Configuration: Pydantic Settings.
-   Package management: uv.
-   Database: PostgreSQL 17 Alpine in Docker Compose.
-   ORM: SQLAlchemy 2.x async.
-   Driver: asyncpg.
-   Migrations: Alembic.
-   Testing: pytest and HTTPX/ASGI-compatible testing.
-   Quality tools: Ruff and mypy.
-   Development and test databases: `atlas_dev` and `atlas_test` on one
    local PostgreSQL server.
-   Artifact binaries: SeaweedFS/S3-compatible object storage.
-   Observability: future OpenTelemetry, Prometheus, Grafana, and Tempo.
-   Microservices: explicitly deferred until justified.

## 16.2 Work discussed or partially implemented

The following have been discussed and some code has been drafted. The
agent must inspect the repository to determine what is actually present:

-   `uv` project and `src` package layout.
-   FastAPI application entry point.
-   `create_app()` application factory.
-   API router mounted under `/api/v1`.
-   Basic `/health` endpoint.
-   Pydantic Settings configuration.
-   `.env` and `.env.example` conventions.
-   Docker Compose PostgreSQL service.
-   PostgreSQL connection URL.
-   SQLAlchemy async engine factory.
-   Async session factory and request dependency.
-   Lifespan-based engine creation and disposal.
-   Readiness health endpoint design (database + S3).

## 16.3 Immediate configuration baseline

The intended local `.env` shape is:

``` dotenv
APP_NAME=Atlas ML Platform
APP_ENV=development
DEBUG=true
LOG_LEVEL=DEBUG

POSTGRES_USER=atlas
POSTGRES_PASSWORD=atlas_dev_password
POSTGRES_DB=atlas_dev

DATABASE_URL=postgresql+asyncpg://atlas:atlas_dev_password@localhost:5432/atlas_dev
DATABASE_ECHO=false

DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
```

Do not assume the PostgreSQL volume was initialized with these
credentials. Verify the actual container and database state first.

## 16.4 Immediate next implementation sequence

1.  Inspect current `.env`, `.env.example`, `config.py`, and
    `docker-compose.yml` without exposing secrets.
2.  Align Compose interpolation variables and `DATABASE_URL`.
3.  Validate Compose configuration.
4.  Verify PostgreSQL container health and actual database/user.
5.  Ensure `atlas_test` exists.
6.  Verify SQLAlchemy engine/session configuration.
7.  Integrate engine creation and disposal into lifespan.
8.  Implement and test the readiness health endpoint (database + S3).
9.  Add a test that proves the application is using the test database.
10. Proceed to ORM Base and Alembic.

Suggested verification commands:

``` bash
docker compose config --quiet
docker compose ps
docker compose logs --tail=100 postgres
docker compose exec postgres pg_isready -U atlas -d atlas_dev
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Do not paste command output containing passwords or other secrets.

------------------------------------------------------------------------

# 18. Risks, Trade-offs, and Open Questions

## 17.1 Risks

### Overengineering

Adding Redis, Kafka, Kubernetes, microservices, and multiple databases
before the core workflow exists will slow learning and increase
operational burden.

Mitigation: follow milestones and introduce infrastructure only when a
concrete requirement exists.

### ML artifact security

Some serialization formats can execute code during deserialization.

Mitigation: trusted artifact provenance, checksum verification,
restricted upload policy, and safe runtime isolation.

### Database connection exhaustion

Pool settings multiply across worker processes and replicas.

Mitigation: calculate total connection budgets and monitor pool
utilization.

### Async event-loop blocking

CPU-heavy inference can block the API event loop.

Mitigation: use an appropriate bounded thread/process worker strategy or
a separate inference worker when justified.

### Inconsistent model activation

Concurrent activation requests may race.

Mitigation: transactional updates, database constraints, and concurrency
tests.

### Observability overhead

Excessive spans, high-cardinality labels, and large payload logs can
create cost and performance problems.

Mitigation: instrument meaningful boundaries, bound label dimensions,
and avoid logging raw payloads.

## 17.2 Open questions to resolve during implementation

These are intentionally not all decided upfront:

1.  Should model versions use semantic versions, monotonically
    increasing integers, or user-defined labels?
2.  Should model artifacts be uploaded through the API, direct presigned
    object-storage URLs, or both?
3.  Which first ML task best demonstrates the inference pipeline?
4.  Should inference be synchronous only initially, with background jobs
    later?
5.  Which model formats are trusted and supported in the first release?
6.  What is the exact retention policy for inference records?
7.  Is authentication needed for the first externally accessible
    deployment?
8.  Which deployment target will be used for the portfolio
    demonstration?
9.  Should MLflow be integrated, or should Atlas own a deliberately
    smaller registry implementation?
10. Which metrics and SLOs are appropriate after baseline load testing?

Resolve these questions when the relevant milestone is reached, not all
at once.

------------------------------------------------------------------------

# 19. Definition of Done

A milestone is complete only when:

-   The intended behavior is implemented.
-   Relevant tests exist and pass.
-   Lint and formatting checks pass for changed code.
-   Type checks pass or any known limitation is documented.
-   Configuration and secrets are handled safely.
-   Failure behavior is understood.
-   Documentation is updated where necessary.
-   The implementation matches the architectural boundaries.
-   The agent reports what was actually verified.
-   The next milestone is clear.

The overall platform is ready for a portfolio demonstration when a user
can register a model, create a version, store an artifact, activate that
version, perform inference, and inspect correlated logs, metrics, and
traces in a reproducible deployment.

------------------------------------------------------------------------

# 20. Glossary

  -----------------------------------------------------------------------
  Term                                Meaning
  ----------------------------------- -----------------------------------
  ASGI                                Asynchronous Server Gateway
                                      Interface, the Python interface
                                      between an async web server and
                                      application

  Application Factory                 A function that constructs and
                                      configures the application

  Lifespan                            Application startup and shutdown
                                      lifecycle

  Domain                              Business concepts, rules, and
                                      invariants

  Use case                            An application operation that
                                      coordinates domain behavior

  Port                                An abstraction describing a
                                      capability required by an inner
                                      layer

  Adapter                             An implementation that connects a
                                      port to a concrete technology

  Repository                          An abstraction for retrieving and
                                      persisting domain objects

  Unit of Work                        A boundary for coordinating changes
                                      within a transaction

  ORM                                 Object-relational mapper

  Migration                           A versioned database schema change

  Connection pool                     A managed collection of reusable
                                      database connections

  Artifact                            A file or binary required to load
                                      or run a model

  Inference                           Executing a trained model to
                                      produce a prediction

  Liveness                            Whether the application process is
                                      alive

  Readiness                           Whether an instance can safely
                                      accept traffic

  Graceful shutdown                   Controlled termination that stops
                                      new work and cleans up resources

  Trace                               A representation of the path of an
                                      operation through a system

  Span                                A timed operation within a trace

  Metric                              A numeric measurement aggregated
                                      over time

  SLO                                 Service Level Objective, a target
                                      for service reliability or
                                      performance

  Cardinality                         The number of distinct values a
                                      metric label can take
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 21. Final Product Direction

Build Atlas as a small but genuinely production-minded ML platform, not
as a collection of fashionable technologies.

The correct sequence is:

1.  Make the application boot reliably.
2.  Make configuration and resource lifecycle predictable.
3.  Make persistence safe and testable.
4.  Build a complete model-registry workflow.
5.  Add versioning and artifact storage.
6.  Serve a real model.
7.  Make the request path observable.
8.  Test reliability and performance.
9.  Harden deployment.
10. Add distributed components only when evidence justifies them.

The central engineering principle is to optimize for **clarity,
correctness, observability, and incremental evolution**. A well-tested
modular monolith with a complete inference workflow is a stronger
foundation than an unfinished microservice architecture.


---

# Appendix A — Instruction to the AI Coding Agent

Treat this PRD as both the product specification and the learning curriculum.
The learner's understanding is the highest priority. Before changing code,
inspect the repository and identify the current milestone and sub-step.
Teach the relevant concept before implementing it. Work in small increments:
one concept, one coherent code change, one focused verification cycle at a
time. Explain what, why, where, and how; trace runtime behavior; discuss
important failure modes and trade-offs; and verify claims with actual
command output or tests.

Do not race through the roadmap, generate entire milestones in one shot,
or move forward just because code compiles. Pause at natural checkpoints.
A milestone is complete only when the product behavior works and the
learner can explain the design, trace its execution, understand its failure
modes, and make a small change independently. If the repository's actual
state differs from this document, report the difference rather than
pretending the planned implementation already exists.

