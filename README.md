# Zenith AI — Backend

Django REST Framework backend for Zenith AI: authentication, conversations, messages, and a server-side connection to a free LLM provider.

[![Tests](https://github.com/DavFilsDev/zenithAI-backend/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/DavFilsDev/zenithAI-backend/actions/workflows/tests.yml)

The product is **free and open to everyone**: no credits, no premium tier, no payment, and a target infrastructure cost of 0 €.

- Frontend repository: `zenithAI_react-typescript-frontend`, served on `http://localhost:5173` in development
- Backend: `http://localhost:8000` in development
- Shared API contract: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md)

## Stack

| | |
|---|---|
| Language | Python 3.11 or newer |
| Framework | Django 5.2, Django REST Framework |
| Authentication | SimpleJWT, bearer tokens |
| API schema | drf-spectacular, Swagger UI and ReDoc |
| Database | PostgreSQL 15 or newer |
| LLM | Google Gemini, through `google-genai` |

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/), which installs the dependencies and the interpreter
- PostgreSQL 15+, running locally
- A free Google Gemini API key, only if you intend to call the chat endpoint

## Local setup

```bash
git clone https://github.com/DavFilsDev/zenithAI-backend.git
cd zenithAI-backend

uv sync

cp .env.example .env
```

`uv sync` creates a `.venv` and installs the exact versions pinned in `uv.lock`. Edit `.env`, then create the database and run the migrations:

```bash
uv run python manage.py migrate
uv run python manage.py runserver
```

The API is then available on `http://localhost:8000`, the admin on `http://localhost:8000/admin/`. Create an admin user with:

```bash
uv run python manage.py createsuperuser
```

## Docker Compose

`docker compose up --build` starts PostgreSQL and the API, applies the migrations and serves the API on `http://localhost:8000`. Set `APP_PORT` to publish a different port. The stack reads `.env` when present and otherwise uses local defaults; the database is kept in the `postgres_data` volume.

The container entrypoint applies the migrations and collects the static files before it starts gunicorn. Docker marks the API healthy when `GET /api/v1/health/live/` succeeds; check it with `docker compose ps`. The liveness probe does not query the database. `GET /api/v1/health/` remains the database readiness check.

The compose stack uses `backend.settings.development`; the image itself defaults to `backend.settings.production`.

## Environment variables

`.env.example` lists every variable the project uses. The settings read today:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django signing key |
| `ALLOWED_HOSTS` | Comma-separated host list |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL connection when `DATABASE_URL` is not set |
| `DATABASE_URL` | PostgreSQL URL; takes precedence over the `DB_*` variables, use the pooled Neon URL in production |
| `DATABASE_URL_UNPOOLED` | Direct PostgreSQL URL used only for migrations when set |
| `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` | Provider selection, key and model for the chat endpoint |
| `LLM_FALLBACK_PROVIDER`, `LLM_FALLBACK_API_KEY`, `LLM_FALLBACK_MODEL` | Second provider used automatically when the primary is rate limited |
| `LLM_PROMPT_BUDGET` | Token budget for the history sent with each request (default 4000) |
| `DAILY_MESSAGE_CAP` | Global maximum messages per day across all users (default 500) |
| `LLM_BREAKER_THRESHOLD`, `LLM_BREAKER_COOLDOWN` | Provider failures that open the circuit breaker and the cool-down in seconds (defaults 5 and 60) |

`CORS_ALLOWED_ORIGINS`, `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_PROMPT_BUDGET`, `DAILY_MESSAGE_CAP` and the `LLM_FALLBACK_*` variables in `.env.example` are the configuration the shared contract requires in section 11. `CORS_ALLOWED_ORIGINS` is read from the environment in phase P0. The `LLM_*` names are the only LLM settings; the legacy `GEMINI_*` names were removed in P2.11.

The frontend runs on `http://localhost:5173` and calls the backend directly, with no proxy, so that origin is the one that must be allowed.

Never commit `.env`. It is already ignored.

## Settings modules

`backend/settings/` is a package:

- `base.py` holds the shared configuration and reads the environment.
- `development.py` sets `DEBUG = True`; `manage.py` uses it by default.
- `production.py` sets `DEBUG = False`, carries the HTTPS/HSTS hardening, serves static files through WhiteNoise, requires `SECRET_KEY`, a database password and `CORS_ALLOWED_ORIGINS`, and validates the LLM configuration at startup; `wsgi.py` and `asgi.py` use it by default.
- `test.py` sets `DEBUG = False`, fast password hashing and an in-memory email backend.

Override the module with `DJANGO_SETTINGS_MODULE`, for example `DJANGO_SETTINGS_MODULE=backend.settings.test uv run python manage.py check`.

## API documentation

With the server running:

- Swagger UI: <http://localhost:8000/api/v1/docs/>
- ReDoc: <http://localhost:8000/api/v1/redoc/>
- OpenAPI schema: <http://localhost:8000/api/v1/schema/>

The generated schema is the source of truth for what exists. The hand-written reference is [`docs/api/api-documentation.md`](docs/api/api-documentation.md), and the target state is [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).

The committed schema snapshot is [`docs/openapi.yml`](docs/openapi.yml). Regenerate it after every API change:

```bash
uv run python manage.py spectacular --file docs/openapi.yml
```

The quality workflow regenerates the snapshot, fails when it differs from the committed file, and requires an update to [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) or [`docs/api/api-documentation.md`](docs/api/api-documentation.md) whenever the schema changes.

## Endpoints available today

| Method | Endpoint | Authentication |
|---|---|---|
| POST | `/api/v1/auth/register/` | No |
| POST | `/api/v1/auth/token/` | No |
| POST | `/api/v1/auth/token/refresh/` | No |
| POST | `/api/v1/auth/logout/` | No |
| GET, PATCH | `/api/v1/auth/profile/` | Yes |
| GET, POST | `/api/v1/chat/conversations/` | Yes |
| GET, PATCH, DELETE | `/api/v1/chat/conversations/{uuid}/` | Yes |
| GET, POST | `/api/v1/chat/conversations/{uuid}/messages/` | Yes |
| POST | `/api/v1/chat/conversations/{uuid}/messages/stream/` (SSE) | Yes |
| GET | `/api/v1/health/` | No |
| GET | `/api/v1/health/live/` | No |
| GET | `/api/v1/schema/`, `/api/v1/docs/`, `/api/v1/redoc/` | No |
| GET | `/admin/` | Staff |

Authentication is a bearer token: `Authorization: Bearer <access_token>`. Access tokens last 15 minutes, refresh tokens 7 days, rotate on use and the rotated token is blacklisted.

Conversation and message ids are UUID strings, list endpoints are paginated with a page size of 20, assistant replies can be streamed as Server-Sent Events, and message sending is throttled per user and per IP. The full list of what is missing is in the improvement plan.

## Project structure

```
backend/     settings package (base, development, production, test) and root URLconf
users/       custom user model, registration, profile
chat/        conversations, messages, selectors, services and the provider-backed LLM (chat/providers/)
docs/        contract, conventions, improvement plan, API documentation
CHANGELOG.md API and behavior changes, versioning per the contract
manage.py
pyproject.toml
uv.lock
.env.example
```

## Tests

```bash
uv run pytest
```

The suite lives in `users/tests.py`, `chat/tests.py`, `chat/providers/tests.py`, `health/tests.py` and `backend/tests.py`: token payloads, refresh-token blacklisting, logout, conversation and message serialization, streaming, provider failures, error envelopes, pagination and schemas. Shared factories and fixtures live in `users/factories.py`, `chat/factories.py` and `conftest.py`. Coverage runs with every test invocation; `users/` and `chat/` are at 100%, and a drop below the 85% floor fails the run.

Every push and pull request runs the suite against PostgreSQL 17 in GitHub Actions (`.github/workflows/tests.yml`). To block a merge on a red run, enable branch protection for `main` and require the `Test` check.

## Code quality

```bash
uv run ruff check .
uv run mypy .
uv run pre-commit run --all-files
```

`ruff` is configured in `pyproject.toml` (import order, naming, pyupgrade, bugbear, simplification and Django rules) at a 120-column limit. `.pre-commit-config.yaml` runs the same checks with autofix, plus YAML/TOML validation, end-of-file, trailing-whitespace, merge-conflict and large-file hooks. Install the hook once with `uv run pre-commit install`.

`mypy` runs with the Django and DRF plugins (`django-stubs`) against `backend.settings.development`; test modules are exempt from the strict untyped-definition rule. Views, serializers, services, providers and models are annotated.

Every pull request and every push to `main` also runs `ruff`, `mypy` and the OpenAPI schema validation in GitHub Actions (`.github/workflows/quality.yml`). Require both the `Test` and `Lint, types and schema` checks under `main` branch protection.

## Deployment (Render Free + Neon Free)

The backend is configured to deploy from [`render.yaml`](render.yaml) to Render's Free web service plan, with PostgreSQL on Neon Free. The target combination costs 0 € and uses no payment method. Free tiers change without notice: re-check the limits before deploying.

### 1. Create the Neon database

1. Create a Neon project in AWS Frankfurt (`eu-central-1`) with PostgreSQL 17.
2. Copy the **pooled** connection string (the host contains `-pooler`) into `DATABASE_URL`.
3. Copy the **direct** connection string into `DATABASE_URL_UNPOOLED`. Migrations use it; the running app uses the pooled URL.
4. Do not use Render Postgres: its free database expires 30 days after creation.

Neon Free includes 100 compute hours per project per month. The liveness endpoint does not query the database, so Render health checks and the uptime monitor do not keep Neon awake.

### 2. Deploy on Render

1. In Render, choose **New → Blueprint**, connect this repository, and select the `main` branch.
2. Apply [`render.yaml`](render.yaml). It creates one Free web service in Frankfurt with:
   - Docker build from `./Dockerfile`
   - health check path `/api/v1/health/live/`
   - `autoDeployTrigger: checksPass`, so a red CI run does not deploy
   - `ALLOWED_HOSTS` set from Render's `RENDER_EXTERNAL_HOSTNAME`
   - a generated `SECRET_KEY`
3. Fill the prompted secrets:
   - `DATABASE_URL` — Neon pooled URL
   - `DATABASE_URL_UNPOOLED` — Neon direct URL
   - `LLM_API_KEY` — Gemini API key
   - `CORS_ALLOWED_ORIGINS` — comma-separated frontend origins, without a trailing slash
4. Keep the service on the **Free** plan and do not add a payment method. Render does not require one for Free web services; stop if the dashboard asks for a card.
5. If the service name `zenith-ai-backend` is unavailable, change the Blueprint `name` and the self-reference under `ALLOWED_HOSTS` together.
6. If you add a custom domain, replace the Blueprint `ALLOWED_HOSTS` self-reference with a literal comma-separated list containing both the `onrender.com` host and the custom domain.

The entrypoint applies migrations and collects static files before gunicorn starts. Render's zero-downtime deploy keeps the previous instance serving until the new one passes its health check, so a failed migration does not replace a working deployment.

### 3. Keep the service warm

Render suspends a Free web service after 15 minutes without traffic. A Free UptimeRobot monitor every 5 minutes keeps it warm:

- Monitor only `https://<service>.onrender.com/api/v1/health/live/`.
- Use an HTTP(s) check with a 5-minute interval and at least one alert contact.
- Never monitor `/api/v1/health/`: it queries Neon and defeats database scale-to-zero.
- A warm service consumes about 744 instance hours per month, below the 750-hour Free allowance. Neon still sleeps when no API request needs it.

Free instances can restart at any time, are limited to 0.1 CPU / 512 MB, and include 5 GB of outbound bandwidth and 500 build-pipeline minutes per month. Render may also suspend a Free service that initiates an unusually high volume of outbound traffic, including database and provider calls. If you exceed bandwidth or pipeline minutes without a payment method, Render suspends Free services or new builds until the next month instead of billing you. This is intentional under the zero-cost rule.

### 4. Verify the deployment

```bash
curl -i https://<service>.onrender.com/api/v1/health/live/
curl -i https://<service>.onrender.com/api/v1/health/
curl -I https://<service>.onrender.com/api/v1/docs/
```

The first endpoint must return `200` without touching Neon. The second may take longer on the first request because it wakes Neon. The third confirms static files and WhiteNoise are working.

Rollback is a Render dashboard action: redeploy a previous successful build. Do not add a paid plan, a persistent disk, or a card to work around a free-tier limit.

## Status & Roadmap

Implemented today:

- Registration, token issuance, token refresh, logout, profile read and update
- Refresh-token rotation with blacklisting and 15-minute access tokens
- Conversation and message CRUD with UUID identifiers, paginated lists
- Message exchange and SSE streaming behind a provider interface (Gemini or Groq), with a configurable fallback provider and a bounded prompt budget
- Per-user and per-IP throttling of message sending (`429 rate_limited` with `Retry-After`)
- A database-backed global daily message cap (`429 quota_exhausted` with `Retry-After`) that survives a restart
- A circuit breaker that fails fast with `503 llm_unavailable` during a provider outage and recovers after a cool-down
- Health check, shared error envelope, Swagger UI, ReDoc and OpenAPI schema
- All endpoints under the versioned base path `/api/v1`
- A pytest suite with factory-boy fixtures and an enforced 85% coverage floor

Planned, in the order of the roadmap:

- CI, containers, and deployment on free hosting with a free PostgreSQL database

Full detail, with effort, acceptance criteria and dependencies:

- [`docs/IMPROVEMENT_PLAN.md`](docs/IMPROVEMENT_PLAN.md) — audit findings, roadmap, free LLM providers, free hosting and the zero-cost rules
- [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) — the API contract shared with the frontend
- [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) — workflow rules and code conventions
- [`docs/api/api-documentation.md`](docs/api/api-documentation.md) — the API that exists today

## Security

Report a vulnerability privately, see [`SECURITY.md`](SECURITY.md). Do not open a public issue for it.

## License

MIT, see [`LICENSE`](LICENSE).

## Author

Fanampinirina Miharisoa David Fils RATIANDRAIBE — <miharisoadavidfils@gmail.com> — <https://github.com/DavFilsDev>
