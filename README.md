# Zenith AI — Backend

Django REST Framework backend for Zenith AI: authentication, conversations, messages, and a server-side connection to a free LLM provider.

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
- PostgreSQL 15+, running locally
- A free Google Gemini API key, only if you intend to call the chat endpoint

## Local setup

```bash
git clone https://github.com/DavFilsDev/zenithAI_django-backend.git
cd zenithAI_django-backend

python -m venv venv
source venv/bin/activate          # macOS and Linux
venv\Scripts\activate             # Windows

pip install -r requirements.txt

cp .env.example .env
```

Edit `.env`, then create the database and run the migrations:

```bash
python manage.py migrate
python manage.py runserver
```

The API is then available on `http://localhost:8000`, the admin on `http://localhost:8000/admin/`. Create an admin user with:

```bash
python manage.py createsuperuser
```

## Environment variables

`.env.example` lists every variable the project uses. The settings read today:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django signing key |
| `DEBUG` | `True` in development, `False` in production |
| `ALLOWED_HOSTS` | Comma-separated host list |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL connection |
| `GEMINI_API_KEY` | Free Gemini key, used by the chat endpoint |

`CORS_ALLOWED_ORIGINS`, `LLM_PROVIDER`, `LLM_API_KEY` and `LLM_MODEL` in `.env.example` are the configuration the shared contract requires. They take effect with phase P0 and P2 of the improvement plan. Until then the CORS origins are hardcoded in the settings and the provider is read from `GEMINI_API_KEY`.

The frontend runs on `http://localhost:5173` and calls the backend directly, with no proxy, so that origin is the one that must be allowed.

Never commit `.env`. It is already ignored.

## API documentation

With the server running:

- Swagger UI: <http://localhost:8000/api/docs/>
- ReDoc: <http://localhost:8000/api/redoc/>
- OpenAPI schema: <http://localhost:8000/api/schema/>

The generated schema is the source of truth for what exists. The hand-written reference is [`docs/api/api-documentation.md`](docs/api/api-documentation.md), and the target state is [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).

To regenerate the schema into a file:

```bash
python manage.py spectacular --file schema.yml
```

## Endpoints available today

| Method | Endpoint | Authentication |
|---|---|---|
| POST | `/api/auth/register/` | No |
| POST | `/api/auth/token/` | No |
| POST | `/api/auth/token/refresh/` | No |
| GET, PATCH, PUT | `/api/auth/profile/` | Yes |
| GET, POST | `/api/chat/conversations/` | Yes |
| GET, PATCH, PUT, DELETE | `/api/chat/conversations/{id}/` | Yes |
| POST | `/api/chat/chat/` | Yes |
| POST | `/api/chat/chat/{conversation_id}/` | Yes |
| GET | `/api/schema/`, `/api/docs/`, `/api/redoc/` | No |
| GET | `/admin/` | Staff |

Authentication is a bearer token: `Authorization: Bearer <access_token>`. Access tokens last 1 day, refresh tokens 7 days and rotate on use.

Ids are integers, lists are not paginated, and there is no logout, no streaming and no throttling yet. The full list of what is missing is in the improvement plan.

## Project structure

```
backend/     settings and root URLconf
users/       custom user model, registration, profile
chat/        conversations, messages, LLM service
docs/        contract, conventions, improvement plan, API documentation
manage.py
requirements.txt
.env.example
```

## Tests

```bash
python manage.py test
```

The suite is currently empty: `users/tests.py` holds the default Django placeholder and there is no `chat/tests.py`, so the command passes while running zero tests. Writing them is task P3.6 of the improvement plan.

## Status & Roadmap

Implemented today:

- Registration, token issuance, token refresh, profile read and update
- Conversation creation, listing, read, update, delete
- Message exchange with a server-side Gemini key
- Swagger UI, ReDoc and OpenAPI schema

Planned, in the order of the roadmap:

- Removal of `is_premium`, the per-user API key and the dead token counter
- Shorter access tokens, working refresh blacklisting, logout
- UUID identifiers, then the `/api/v1/` base path, message sub-resource, pagination, health check and a shared error envelope
- A provider interface with a second free provider, SSE streaming, throttling and a global daily cap
- Tooling: `pyproject.toml`, ruff, mypy, pytest, coverage, pre-commit
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
