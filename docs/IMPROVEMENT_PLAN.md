# Improvement Plan

Audit, decisions and roadmap for the Zenith AI backend. The API target state is defined in [`docs/API_CONTRACT.md`](API_CONTRACT.md) and is shared with the frontend repository. The API that exists today is documented in [`docs/api/api-documentation.md`](api/api-documentation.md). Workflow rules are in [`docs/CONVENTIONS.md`](CONVENTIONS.md).

Product constraints, applied to every task below: 100% free, open to everyone, no credits, no premium, no payment, target infrastructure cost 0 €.

## 1. Audit findings

Every claim below was read in the code, not inferred from the documentation.

### 1.1 Routes actually exposed

Source: `backend/urls.py`, `users/urls.py`, `chat/urls.py`.

| Method and path | Permission | View |
|---|---|---|
| `POST /api/auth/register/` | `AllowAny` | `users/views.py:56-64` |
| `POST /api/auth/token/` | `AllowAny` (SimpleJWT) | `users/urls.py:7` |
| `POST /api/auth/token/refresh/` | `AllowAny` | `users/urls.py:8` |
| `GET, PUT, PATCH /api/auth/profile/` | `IsAuthenticated` | `users/views.py:98-183` |
| `GET, POST /api/chat/conversations/` | `IsAuthenticated` | `chat/views.py:13-34` |
| `GET, PUT, PATCH, DELETE /api/chat/conversations/<int:pk>/` | `IsAuthenticated` | `chat/views.py:113-132` |
| `POST /api/chat/chat/` | `IsAuthenticated` | `chat/urls.py:7` |
| `POST /api/chat/chat/<int:conversation_id>/` | `IsAuthenticated` | `chat/urls.py:8` |
| `GET /api/v1/schema/`, `/api/v1/docs/`, `/api/v1/redoc/` | public | `backend/urls.py:13-15` |
| `GET /admin/` | staff | `backend/urls.py:6` |

Findings:

- No logout, no health check, no message sub-resource, no streaming endpoint, no pagination, no throttling.
- The default permission is `IsAuthenticated` (`backend/settings.py:122-124`), and the two token endpoints opt out through SimpleJWT itself rather than through an explicit declaration.
- `SERVE_INCLUDE_SCHEMA: False` (`backend/settings.py:153`) means the schema is served at `/api/schema/` and not at `/api/schema/?format=openapi`. The documentation never stated this.
- P0.17 removed the "ChatGPT-like" / "Credit system" wording from the schema description and aligned the model name with the configured `gemini-2.5-flash`.

### 1.2 Models

Source: `users/models.py`, `chat/models.py`, `backend/settings.py:106`, `users/migrations/0001_initial.py`.

| Model | Real fields | Finding |
|---|---|---|
| `User` | `email` unique (`USERNAME_FIELD`), `username` still required, `api_key`, `credits=10`, `is_premium` | `api_key` is never written nor read: plaintext secret storage with no use. `credits` is never decremented and never checked: cosmetic. `is_premium` is never enforced. |
| `UserProfile` | `theme`, `language`, timestamps | Orphan. No serializer, no view, no signal. Admin only (`users/admin.py:24-29`). |
| `Conversation` | `id` BigAutoField, `user`, `title`, timestamps | Integer PK. |
| `Message` | `id` BigAutoField, `conversation`, `role`, `content`, `tokens=0` | `tokens` is never populated, always `0` in every response. Integer PK. |

Other model findings:

- `REQUIRED_FIELDS = ['username']` (`users/models.py:11`) keeps `username` mandatory while `USERNAME_FIELD` is `email`: two accounts can differ only by email case, because `email` uniqueness is case-sensitive and unnormalised.
- `credits` and `is_premium` are exposed in the token response (`users/views.py:36-37`) and the profile, and the frontend displays credits as read-only text. Removing them is a cross-repository change.
- No email verification. Registration creates a usable account immediately.

### 1.3 Third-party applications and dependencies

- `dj-rest-auth==7.0.2` and `django-allauth==65.14.1` are in `requirements.txt:10,12` but are **not** in `INSTALLED_APPS` (`backend/settings.py:17-34`), have no middleware, no configuration, and are imported nowhere. They are dead dependencies.
- `openai==2.21.0` (`requirements.txt:35`) is installed and never imported. It becomes useful in P2, as the Groq API is OpenAI-compatible.
- `websockets==16.0` (`requirements.txt:59`) is installed and never imported. WebSocket is not part of the contract.
- `google-ai-generativelanguage==0.6.15` (`requirements.txt:17`) is the legacy SDK, superseded by `google-genai`, which is the one actually used (`chat/services.py:1`).
- No test, lint, type or coverage tooling is declared at all.

### 1.4 LLM integration

Source: `chat/services.py`, `chat/views.py:381-446`.

- The only provider is Google Gemini, through `google-genai`.
- The call is **synchronous and blocking** inside a DRF view: `gemini_service.generate_response(...)` at `chat/views.py:426` holds a worker for the whole generation.
- `gemini_service = GeminiService()` runs at import time (`chat/services.py:113`), and `__init__` calls `_test_connection()` (`chat/services.py:35,40-47`), which performs a **live API call at import**. Importing `chat.views` (`chat/views.py:8`) therefore makes `migrate`, `collectstatic` and every management command perform a network request, and fail slowly when offline.
- The full history is loaded on every turn (`chat/views.py:421-423`) and flattened into a single prompt (`chat/services.py:68-74`), so prompt size grows without bound and the role structure is lost.
- `max_output_tokens` is hardcoded to 2048 (`backend/settings.py:180`) and is not configurable per model.
- Provider errors are converted into HTTP **200** responses whose body is an error sentence stored as an assistant message (`chat/services.py:99-109`, persisted at `chat/views.py:429-433`). The frontend displays it as a normal answer, and it becomes part of the conversation history. There is no `llm_unavailable` code and no 5xx.
- The system prompt is a class constant (`chat/services.py:20-26`), not configurable.

### 1.5 Authentication

Source: `backend/settings.py:128-134`, `users/urls.py`.

- Access token lifetime is **1 day** (`backend/settings.py:130`), against a 15-minute target. A leaked access token stays usable for up to 24 hours.
- `ROTATE_REFRESH_TOKENS: True` and `BLACKLIST_AFTER_ROTATION: True` are set, but `rest_framework_simplejwt.token_blacklist` is **not** in `INSTALLED_APPS` (`backend/settings.py:17-34`). Blacklisting is therefore silently inert: rotation happens, old refresh tokens stay valid for their full 7 days.
- No logout endpoint, so no token can ever be revoked. The frontend logout only clears `localStorage` (`src/services/tokenManager.ts` in the frontend repository).
- No throttling, no brute-force protection, no lockout on the login endpoint.
- Profile `PUT` and `PATCH` allow changing `email` and `username` (`users/serializers.py:7-11`) with no verification step.

### 1.6 Configuration and production hardening

Source: `backend/settings.py`.

- `SECRET_KEY` falls back to a hardcoded insecure value (`backend/settings.py:11`). Nothing fails when it is still the default.
- A real-looking database password is committed in the settings default (`backend/settings.py:73`).
- `CORS_ALLOWED_ORIGINS` is defined in the env template and read nowhere. Origins are hardcoded (`backend/settings.py:109-114`) and include port 3000, which the frontend does not use (its dev server is 5173).
- `CORS_ALLOW_CREDENTIALS = True` (`backend/settings.py:115`) is not needed, since auth is a bearer header.
- `GEMINI_MODEL` is declared in the env template and read nowhere; the model is hardcoded (`backend/settings.py:176`).
- `DEBUG` defaults to `False` (`backend/settings.py:13`), which is the right default.
- `ALLOWED_HOSTS` defaults to `localhost,127.0.0.1` (`backend/settings.py:15`), which is safe but means a misconfigured deployment fails silently rather than loudly.
- No `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS` or `USE_X_FORWARDED_HOST`. The admin is reachable over plain HTTP in production.
- `LOGGING` is not configured. Two loggers exist (`chat/views.py:11`, `chat/services.py:6`) with no handler, so on a deployed instance nothing is captured.
- A single settings module serves dev and prod.
- `.gitignore:26` still ignores `docker-compose.override.yml` although Docker was removed from the project.

### 1.7 Queryset scoping, id types, payload shape

- Querysets are correctly scoped to the current user: `chat/views.py:28-30`, `chat/views.py:130-132`, `chat/views.py:397-401`. **No IDOR exists today.** Any new endpoint that skips this filter would introduce one, so the rule is written into the conventions.
- Object access goes through the filtered queryset, so a conversation owned by somebody else returns `404`, not the `403` documented in the schema examples (`chat/views.py:146-151`, `chat/views.py:195-198`).
- Public ids are UUIDs on `Conversation` and `Message`: a `uuid` field with a DB constraint, payloads carry `uuid` instead of `id`, and URL converters are `<uuid:uuid>` / `<uuid:conversation_id>` (`chat/urls.py:6,8`). The frontend types them as `string` (`src/types/chat.ts`, `src/types/user.ts` in the frontend repository), so the switch is a type-level fix on both sides.
- `ConversationSerializer` embeds the full message list of a **single** conversation (`chat/serializers.py:33`). The list endpoint uses `ConversationListSerializer` with an annotated `message_count`, so `GET /conversations/` runs a constant number of queries whatever the history size (`chat/serializers.py:10-19`, `chat/views.py:20-24`).
- The payload omits `user` on a conversation and `conversation` on a message, which the frontend types declare (`src/types/chat.ts`).
- `message_count` is sent but never read by the frontend.
- The login response returns `access`, `refresh`, `user_id`, `email`, `username`, `credits`, `is_premium` (`users/views.py:30-38`), while the frontend expects a nested `user` object and fetches `/auth/profile/` as a second request.
- Registration returns only `RegisterSerializer` output, `{email, username}` (`users/views.py:65`), with no tokens, so the frontend has to log in again.
- The OpenAPI schema derives `conversation_id` from the URL converter `<uuid:conversation_id>` and only on the route where it exists; the base `POST /chat/` no longer declares a path parameter (P0.17).

### 1.8 Tests

- `users/tests.py` contains only the default Django placeholder. There is no `chat/tests.py`.
- `python manage.py test` and `python manage.py test users` succeed while running **zero** tests, which makes the testing section of the README misleading.
- No provider fake exists, so any future test of the chat path would attempt a real Gemini call.

### 1.9 Documentation accuracy

- `README.md:1-3` titles the project "Backend Repository README" and "Chatbot Platform"; `README.md:42` shows the folder as `chatgpt-backend/`.
- `README.md:25` tells the reader to run `cp .env.example .env`, but the file is `.example.env`. The command fails.
- `README.md:98,107` uses the database name `chatgpt_db`; settings default to `zenith_ai_db`.
- `README.md:103` shows `CORS_ALLOWED_ORIGINS=http://localhost:3000`; the frontend dev server runs on 5173.
- `README.md:124-126` links Swagger, ReDoc and the schema as relative paths, which are broken when the README is read on GitHub.
- `README.md:132` documents a 1-day access token, accurate today, but not the contract target.
- `README.md:136-152` documents credits, premium and API key storage.
- `README.md:165-191` documents Railway, Render and Fly.io deployments. Fly.io no longer has a free tier, and none of those commands has been run from this repository.
- `README.md:213` sends the reader to a Wiki that is not part of the repository.
- `README.md:94-104` omits `GEMINI_API_KEY`, without which every chat request returns an unavailable message.
- `docs/api/api-documentation.md:1` writes the product "ZenithAI", the contract writes "Zenith AI".
- `docs/api/api-documentation.md:41-49` shows a login response with only `access` and `refresh`, omitting the four extra keys actually returned.
- `docs/api/api-documentation.md:28` uses `password123` as a registration example, which is rejected by `CommonPasswordValidator`.
- `docs/api/api-documentation.md` omits the token refresh endpoint, `PUT`/`PATCH` on the profile, `PUT`/`PATCH`/`DELETE` on a conversation, and the documentation endpoints.

### 1.10 Postman collection gaps

`docs/api/zenith-ai-api.postman_collection.json` is left untouched by this step. Differences with the real API, to fix in P1:

- Collection name and environment name say "ZenithAI" instead of "Zenith AI".
- `base_url` is `http://127.0.0.1:8000`; the documented dev backend is `http://localhost:8000`.
- `Update User Profile` uses `PUT`; the contract only allows `GET` and `PATCH`.
- `Update Conversation` uses `PUT`; same.
- No `PATCH` request for the profile, and none for a conversation.
- `conversation_id` is hardcoded to `1` in the environment and in the URLs of the conversation and chat requests. It is never written back from a create response.
- No assertion anywhere except two on the login request: status codes and response shapes are unchecked.
- No request for the OpenAPI schema, Swagger, or ReDoc.
- Missing every contract endpoint: `POST /auth/logout/`, `GET /health/`, `GET /conversations/{uuid}/messages/`, `POST /conversations/{uuid}/messages/`, `POST /conversations/{uuid}/messages/stream/`.
- It encodes the current chat routes `POST /api/chat/chat/` and `POST /api/chat/chat/1/`, which P1 removes.
- No pagination parameters, so the DRF envelope change in P1 is not exercised.
- No 401, 404, 429 or error-envelope examples.

## 2. Assumptions

1. The author of record is Fanampinirina Miharisoa David Fils RATIANDRAIBE (`README.md:214`), used for the MIT license, with the current year.
2. Contact address for the license and the security policy is the address already published in the README.
3. Registration keeps `email`, `username`, `password` and `password2`. The contract does not enumerate the payload, and the frontend already sends those four fields.
4. The contract describes the target. The legacy routes stay alive until P1, then they are cut in one step, in the same release as the frontend change that adopts `/api/v1/`.
5. Conversation payloads drop `user`, and message payloads drop `conversation`: both are implied by the endpoint. The frontend types are updated in the same release.
6. Email verification is out of scope for this plan. It is a known limitation and is documented as one until it is scheduled.
7. No managed Redis is assumed, because every candidate is either paid or has a sleep-based free tier. Throttling and quota state therefore live in the database or in process memory, which means a single application instance. Moving to several instances requires revisiting this decision.
8. Free-tier figures were verified on 2026-10-01 against official documentation and secondary sources. They change without notice and are re-checked before each deployment.
9. Documentation is written in English. No AI agent configuration file is added to this repository; the rules live in `docs/`.
10. The frontend repository is a separate codebase. Every change that breaks it is called out in the plan and must be done in both repositories.
11. `Message.tokens` is removed rather than populated: no free provider returns a reliable per-request count through the SDK, and no code reads the value.
12. The `UserProfile` model is removed rather than exposed: nothing reads `theme` or `language`, and the frontend applies its own theme.

## 3. Roadmap

Effort: **S** under half a day, **M** one to three days, **L** more than three days.

### P0 — Security and model cleanup

- [x] **P0.1** Remove `User.credits` from the model, the serializers, the admin and the token response. — *S* — `GET /auth/profile/`, `POST /auth/token/` and the OpenAPI schema contain no `credits`; the frontend profile modal no longer renders a credit counter; the Django admin has no credits column. — Depends on: frontend change, same release.
- [x] **P0.2** Remove `User.is_premium` everywhere. — *S* — no occurrence of `is_premium` remains in the backend, the schema is clean, the admin no longer offers a premium field. — Depends on: nothing.
- [x] **P0.3** Remove `User.api_key`. — *S* — the column is dropped, no per-user key exists anywhere, the schema exposes no key field. — Depends on: nothing.
- [x] **P0.4** Delete the `UserProfile` model and its admin registration. — *S* — the table is dropped by a migration, `users/models.py` only holds `User`. — Depends on: nothing.
- [x] **P0.5** Remove `Message.tokens` from the model and the serializer. — *S* — no message payload contains a token count, the admin inline is updated, the schema is clean. — Depends on: nothing.
- [x] **P0.6** Add `rest_framework_simplejwt.token_blacklist` to `INSTALLED_APPS` so `BLACKLIST_AFTER_ROTATION` takes effect. — *S* — refreshing twice with the same refresh token returns `401` the second time; a blacklisted token is rejected. — Depends on: P0.7.
- [x] **P0.7** Set `ACCESS_TOKEN_LIFETIME` to 15 minutes. — *S* — a token issued now expires in 15 minutes; the frontend refresh interceptor covers the transition without a user-visible logout. — Depends on: nothing.
- [x] **P0.8** Add a logout endpoint that blacklists the presented refresh token. — *M* — `POST /api/auth/logout/` returns `204` with `{"refresh"}`, the token is unusable afterwards, and a blacklisted refresh token on `/api/auth/token/refresh/` returns `401`. — Depends on: P0.6.
- [x] **P0.9** Move to UUID public ids for `Conversation` and `Message`. — *M* — every public id is a UUID string, URLs use `<uuid:pk>`, an integer id returns `404`, the frontend types match. — Depends on: nothing.
- [x] **P0.10** Fail fast on an insecure configuration. — *S* — starting with `DEBUG=False` and the default `SECRET_KEY`, or with an empty `SECRET_KEY` in production, raises `ImproperlyConfigured` instead of serving traffic. — Depends on: nothing.
- [x] **P0.11** Remove the database password default from the settings and require the variable. — *S* — no credential literal remains in `backend/settings.py`, a missing `DB_PASSWORD` raises `ImproperlyConfigured` outside development. — Depends on: P0.9.
- [x] **P0.12** Read `CORS_ALLOWED_ORIGINS` from the environment instead of hardcoding origins. — *S* — the value in `.env` is the only source of truth, port 3000 is gone, a missing variable in production fails loudly. — Depends on: nothing.
- [x] **P0.13** Build the Gemini client lazily, without any network call at import. — *S* — `migrate`, `collectstatic` and `showmigrations` work with the network disabled; no request is issued when the module is imported. — Depends on: nothing.
- [x] **P0.14** Remove the dead dependencies. — *S* — `dj-rest-auth`, `django-allauth`, `websockets` and `google-ai-generativelanguage` leave `requirements.txt`; `openai` stays only if P2 uses it, otherwise it leaves too. — Depends on: nothing.
- [x] **P0.15** Add the production security settings. — *M* — `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_PROXY_SSL_HEADER` and `USE_X_FORWARDED_HOST` are set when `DEBUG` is off; the admin is only reachable over HTTPS. — Depends on: P3.9.
- [x] **P0.16** Normalise emails and make uniqueness case-insensitive. — *S* — `Foo@Example.com` and `foo@example.com` are the same account, and a `UniqueConstraint(Lower('email'))` is in place. — Depends on: nothing.
- [x] **P0.17** Correct the OpenAPI metadata. — *S* — the description no longer mentions ChatGPT or credits, the model name matches the configuration, and `conversation_id` is no longer declared as a path parameter. — Depends on: nothing.
- [x] **P0.18** Stop returning provider errors as successful assistant messages. — *S* — a provider failure returns `503 llm_unavailable`, nothing is persisted as an assistant message, and the raw provider error never reaches the client. — Depends on: P0.13.
- [x] **P0.19** Bound the conversation list payload. — *M* — listing conversations no longer embeds every message, the number of queries per request is constant, and the payload stops growing with history. — Depends on: nothing.
- [x] **P0.20** Clean the leftovers: remove the Docker entry from `.gitignore` and the unused `UserProfile` references from the admin. — *S* — `.gitignore` contains no Docker entry; the admin imports cleanly. — Depends on: P0.4.

### P1 — Migration to contract v1

- [ ] **P1.1** Mount the `/api/v1/` namespace. — *M* — every contract path resolves under `/api/v1/`, and the OpenAPI `servers` entry points at `/api/v1`. — Depends on: P0.
- [ ] **P1.2** Restructure chat as REST resources, with messages nested under a conversation. — *M* — `GET,POST /conversations/`, `GET,PATCH,DELETE /conversations/{uuid}/` and `GET,POST /conversations/{uuid}/messages/` all exist, and `POST /conversations/{uuid}/messages/` returns the complete assistant message. — Depends on: P1.1, P0.9.
- [ ] **P1.3** Enable pagination with a page size of 20 on every list endpoint. — *S* — list responses use the `{count, next, previous, results}` envelope and a client-supplied `page_size` above 20 is capped. — Depends on: P1.2.
- [x] **P1.4** Add the shared error envelope through a custom DRF exception handler. — *M* — every error response, including validation, throttling, 404 and 500, matches `{"error": {"code", "message", "details"}}` with the codes defined in the contract. — Depends on: nothing.
- [x] **P1.5** Add `GET /api/v1/health/`. — *S* — the endpoint is public, returns `200` with the database check result, and does not require a token. — Depends on: P1.1.
- [x] **P1.6** Serve the documentation under `/api/v1/docs/`, `/api/v1/redoc/` and `/api/v1/schema/`. — *S* — all three paths load and the schema validates with `manage.py spectacular --validate`. — Depends on: P1.1.
- [ ] **P1.7** Restrict the profile to `GET` and `PATCH`. — *S* — `PUT /auth/profile/` returns `405`, and the schema no longer advertises it. — Depends on: P1.1.
- [ ] **P1.8** Fix the resource payloads. — *M* — conversation and message fields match what the contract and the frontend types declare, no field is sent that the frontend never reads, and `message_count` is declared once. — Depends on: P0.19.
- [ ] **P1.9** Cut the legacy routes. — *S* — `/api/auth/` and `/api/chat/` return `404`, the OpenAPI schema lists only `/api/v1` paths, and the README and documentation mention no legacy path. — Depends on: P1.2, P1.7, frontend release.
- [ ] **P1.10** Rewrite the Postman collection and environment. — *M* — every contract endpoint is covered, `conversation_id` is captured from the create response instead of being hardcoded, and pagination, 401, 404, 429 and the error envelope are asserted. — Depends on: P1.9.
- [ ] **P1.11** Move logout to the contract path. — *S* — `POST /api/v1/auth/logout/` blacklists the refresh token, the frontend logout call is updated in the same release. — Depends on: P0.8, P1.1.
- [ ] **P1.12** State the versioning and deprecation policy. — *S* — the contract documents that a breaking change requires `/api/v2/`, a notice in the changelog, and an update to both repository copies. — Depends on: P1.9.

### P2 — LLM abstraction, free provider, streaming and limits

- [ ] **P2.1** Define the provider interface. — *M* — a single protocol with `generate` and `stream`, no framework import, so a fake can replace it in tests. — Depends on: nothing.
- [ ] **P2.2** Extract the Gemini implementation behind the interface. — *M* — behaviour is unchanged, no provider import leaks into views, and the system prompt becomes configuration. — Depends on: P2.1, P0.13.
- [ ] **P2.3** Add the Groq implementation. — *S* — the same interface is implemented on the OpenAI-compatible endpoint, selected by `LLM_PROVIDER=groq` and `LLM_MODEL`. — Depends on: P2.1.
- [ ] **P2.4** Add a provider factory with fallback. — *M* — `LLM_PROVIDER`, `LLM_API_KEY` and `LLM_MODEL` are the only settings, a missing key fails at startup with a clear message, and a second provider can be used automatically when the first is rate limited. — Depends on: P2.2, P2.3.
- [ ] **P2.5** Add SSE streaming. — *L* — `POST /conversations/{uuid}/messages/stream/` emits `token`, `done` and `error` events in the contract format, the assistant message is persisted once at the end, and a client that disconnects mid-stream does not leave an orphan row. — Depends on: P1.2.
- [ ] **P2.6** Bound the prompt. — *M* — only the most recent turns within a token budget are sent, the total prompt size stops growing with the history length, and the budget is configurable. — Depends on: P2.2.
- [ ] **P2.7** Map provider errors to contract codes. — *S* — a provider 429 becomes `llm_unavailable` with a `Retry-After` header, an invalid key is reported as a configuration error at startup, and no raw provider text reaches the client. — Depends on: P1.4.
- [ ] **P2.8** Add throttling per IP and per user. — *M* — DRF throttle scopes are configured, exceeding a limit returns `429 rate_limited` with `Retry-After`, and the limit is documented in the contract. — Depends on: P1.4.
- [ ] **P2.9** Add a global daily cap. — *M* — a global counter caps requests per day across all users, exhaustion returns `429 quota_exhausted`, the counter resets daily, and the state survives a restart. — Depends on: P2.8.
- [ ] **P2.10** Add a circuit breaker around the provider. — *M* — repeated provider failures open the circuit, subsequent calls fail fast with `llm_unavailable` instead of waiting for a timeout, and the circuit closes again after a cool-down. — Depends on: P2.7.
- [ ] **P2.11** Remove the legacy Gemini settings names. — *S* — no `GEMINI_API_KEY` or `GEMINI_MODEL` setting remains, `.env.example` only carries the `LLM_*` names. — Depends on: P2.4.

### P3 — Quality

- [ ] **P3.1** Move to `pyproject.toml` with a lock file. — *M* — dependencies are declared in `pyproject.toml`, a lock file is committed, and an install is reproducible from the lock alone. — Depends on: nothing.
- [ ] **P3.2** Add ruff. — *S* — lint runs in one command, the import and naming rules from the conventions are enabled, and existing violations are fixed in the same commit. — Depends on: P3.1.
- [ ] **P3.3** Add mypy with django-stubs. — *M* — type checking passes on `users/` and `chat/`, and views and serializers are annotated. — Depends on: P3.1.
- [ ] **P3.4** Replace the Django test runner with pytest-django. — *M* — `pytest` is the single entry point, no database is created by hand, and the existing placeholder tests are replaced by real ones. — Depends on: P3.1.
- [ ] **P3.5** Add factory_boy fixtures. — *M* — user, conversation and message fixtures exist, a test creating a conversation is a single line, and no test hardcodes an id. — Depends on: P3.4.
- [ ] **P3.6** Reach 85% coverage on `users/` and `chat/`, and enforce it. — *M* — every endpoint has happy-path, unauthenticated, wrong-owner and validation cases, and the threshold fails the build when it drops. — Depends on: P3.5.
- [ ] **P3.7** Add pre-commit. — *S* — ruff, the import sorter and the basic hygiene hooks run on commit, and a failing hook blocks the commit. — Depends on: P3.2.
- [ ] **P3.8** Move to psycopg 3. — *S* — `psycopg2-binary` is replaced by `psycopg[binary]`, the connection works on the development and production databases. — Depends on: nothing.
- [ ] **P3.9** Split settings into base, development, production and test. — *M* — each environment has its own module, the production one contains the hardening from P0.15, and no development value can leak into production. — Depends on: P0.15, P0.12.
- [ ] **P3.10** Extract selectors and complete the service layer. — *M* — read queries live in `selectors.py` and are the single place where ownership is filtered, use cases live in `services.py`, and no view builds a queryset or calls a provider. — Depends on: P0.19.
- [ ] **P3.11** Apply the comment policy to the existing code. — *M* — no decorative comment and no docstring that only restates a name remains, and every remaining comment explains a non-obvious reason. — Depends on: nothing.
- [ ] **P3.12** Add type hints to views, serializers and services. — *M* — every public function is annotated, and mypy runs clean. — Depends on: P3.3.

### P4 — Continuous integration and containers

- [ ] **P4.1** Add the CI test workflow. — *M* — every push and pull request runs the full suite against a PostgreSQL service, and the workflow is required before merge. — Depends on: P3.4.
- [ ] **P4.2** Add the CI lint and type-check workflow. — *S* — ruff, mypy and the schema validation run on every pull request. — Depends on: P3.2, P3.3.
- [ ] **P4.3** Add a schema drift check. — *S* — CI fails when the generated OpenAPI schema changes without a matching change in `docs/API_CONTRACT.md` or in the API documentation. — Depends on: P1.6, P3.7.
- [ ] **P4.4** Write the Dockerfile. — *M* — the image runs as a non-root user, runs on a supported Python version, and starts with gunicorn or uvicorn. — Depends on: P3.1, P3.9.
- [ ] **P4.5** Add a compose file with the application and PostgreSQL. — *S* — `docker compose up` gives a working local stack with migrations applied and no manual step. — Depends on: P4.4.
- [ ] **P4.6** Add the container entrypoint and health check. — *S* — the container applies migrations, collects static files, then starts the server, and the health check hits `GET /api/v1/health/`. — Depends on: P4.4, P1.5.

### P5 — Free deployment and free observability

- [ ] **P5.1** Deploy the backend on Koyeb. — *M* — the service is reachable on HTTPS, the health check is wired, and the bill stays at zero. — Depends on: P4.4, P0.15.
- [ ] **P5.2** Attach a Neon free PostgreSQL database. — *M* — the pooled connection string is configured, migrations run on it, and the plan is not exceeded. — Depends on: P1.1, P3.8.
- [ ] **P5.3** Generate and store the production configuration. — *S* — a strong `SECRET_KEY` is generated, `DEBUG=False`, `ALLOWED_HOSTS` lists the deployed host only, and no secret is committed. — Depends on: P0.10, P0.11.
- [ ] **P5.4** Automate the release. — *M* — a push to the main branch migrates and restarts, and a failed migration leaves the previous version serving. — Depends on: P5.1, P5.2.
- [ ] **P5.5** Configure free error monitoring. — *S* — provider and server errors are reported to a free tier service, with the environment and the route attached, and personal data excluded. — Depends on: P5.1.
- [ ] **P5.6** Configure an uptime check. — *S* — the health endpoint is polled from outside, and an alert fires on failure. — Depends on: P1.5.
- [ ] **P5.7** Add structured logging with a request identifier. — *S* — each request logs one line with an id, the user id when authenticated, the route and the duration, and the format is machine-readable. — Depends on: P5.5.
- [ ] **P5.8** Expose quota and limit counters in the admin. — *M* — the global daily counter, the per-user usage and the provider 429 ratio are visible without a database query, so a quota overrun is noticed before users complain. — Depends on: P2.9.
- [ ] **P5.9** Write the deployment runbook. — *M* — the README documents the exact steps to provision a free backend, a free database, the provider key and the environment variables, with no step that requires a paid resource. — Depends on: P5.1, P5.2.

## 4. Free LLM providers

Verified on **2026-10-01**. Free tiers change without notice: re-check the official page before each deployment. Figures are indicative, per project and per model, and depend on usage history.

| Provider | Free tier | Limits | Conditions and risks | Effort to adopt |
|---|---|---|---|---|
| **Google Gemini API** (AI Studio) | Yes, no card | Around 10 RPM and 250 requests/day for `gemini-2.5-flash`, around 15 RPM and 1000 requests/day for `gemini-2.5-flash-lite`, 250k tokens/minute, 1M context. Daily quota resets at midnight Pacific time. | Limits are per project, not per key. Pro models are reported as paid-only since April 2026, **to verify** on the official page. Free-tier prompts may be used to improve Google products: a real privacy caveat for a public app. Already integrated (`chat/services.py`). | Low, already there |
| **Groq** | Yes, no card | Around 30 RPM, 6k to 12k tokens/minute depending on the model, 1000 to 14400 requests/day depending on the model. 429 carries a `Retry-After`. | Limits apply per organisation, so extra keys do not raise them. A paid card unlocks a 10x Developer tier, which must never be added. The API is OpenAI-compatible, so the code path is the same for several providers. | Low, one new class |
| **OpenRouter free models** | Yes, but unusable at this scale | 20 requests/minute and **50 requests/day** while no credits have ever been purchased. 1000 requests/day requires 10 $ of purchased credits, which is forbidden by the zero-cost rule. | Failed attempts count against the daily quota. The `:free` roster changes: a model can disappear. Upstream providers throttle on top of that. Their own documentation states the free tier is not suitable for production. | Medium, and the daily cap is below our needs |

Decision: **Gemini primary, Groq fallback**, behind the single provider interface defined in P2.1. Gemini stays primary because it is already integrated, so P2 carries no migration risk, and its free Flash-Lite quota is the most generous in requests per day; Groq is the fallback because it is a second, independent free quota pool, which is what actually protects a free multi-user service, and because its OpenAI-compatible API makes it almost free to implement. OpenRouter is kept as a documented option only, never as a primary, because reaching a usable daily cap requires a paid purchase.

Quota arithmetic for a 0 € service, to size the limits in P2.9: with Gemini Flash-Lite at roughly 1000 requests per day and Groq at roughly 1000 to 14400 requests per day depending on the model, two providers cover a few thousand messages per day. A global daily cap well below that ceiling, plus throttling, is what turns a shared quota into a service that degrades predictably instead of collapsing.

## 5. Free hosting

Verified on **2026-10-01**. Same caveat: re-check before deploying.

| Platform | Free offer | Known limits | Verdict |
|---|---|---|---|
| **Koyeb** | One free web service, 512 MB RAM, 0.1 vCPU, 2 GB SSD, never charged. 100 GB egress per month. | The free PostgreSQL is limited to about 5 hours of active time and 1 GB, so it cannot be used. 0.1 vCPU is tight: it rules out multiple worker processes, which reinforces assumption 7. Acquired by Mistral AI in February 2026, so the roadmap is a risk. | **Recommended backend** |
| **Render** | Free web service with 750 instance hours per month, free static sites. | Spins down after 15 minutes of inactivity, cold start around 30 to 60 seconds. Ephemeral filesystem. The free PostgreSQL **expires 30 days after creation**, so it is only good for a prototype. | Fallback backend |
| **Neon** | 100 projects, 100 compute hours per project per month, 0.5 GB storage per project, 5 GB public transfer per month. | Compute scales to zero after 5 minutes, waking in a few hundred milliseconds, and that cannot be disabled. When the compute hours or the transfer run out, the compute is suspended until the next period. No overage is ever billed. | **Recommended database**, use the pooled connection string |
| **Supabase** | 500 MB database, 1 GB file storage, 5 GB bandwidth, two free projects. | A free project is paused after 7 days of low activity, with a 1-year restore window. | Fallback database |
| **Fly.io** | None. | No free tier anymore, pay-as-you-go only, trial credits are temporary. The current README claims it as a free option, which is wrong. | **Excluded** |

Target combination, and what it costs: the backend on Koyeb, the database on Neon, the model provider on Gemini with Groq as fallback. 0 €.

Two consequences of the free tier to design around, not to complain about: a request that wakes a sleeping service is slow, so the health check must be cheap and the LLM call must be the only slow part of a request; and a single small instance means no horizontal scaling, so in-process state such as the quota counter must survive a restart.

## 6. Zero-cost rules

1. No paid dependency, service, plan or card, ever. A card attached to any provider converts a `429` into a charge, which is the single most likely way this project would start costing money.
2. A free tier that improves after a purchase stays unused. OpenRouter's 1000 requests per day is exactly that case.
3. Risks of exceeding a quota, and the countermeasure for each:

| Risk | Consequence | Countermeasure |
|---|---|---|
| Traffic spike on the shared free quota | `429` from the provider for everybody, or a silent degradation | Per-IP and per-user throttling (P2.8) and a global daily cap (P2.9) |
| A single user consuming the daily quota | The service is unusable for the rest of the day | The global cap, plus per-user throttling well below it |
| Provider quota or outage | No answers at all | Circuit breaker (P2.10) and automatic fallback to the second provider (P2.4) |
| Unbounded prompts | The daily quota is burned in minutes | Token budget and history windowing (P2.6) |
| Overrun discovered too late | Users are already affected | Rate-limit and 429 ratio monitoring (P5.8) |
| Provider silently degrades free traffic | Latency spikes, timeouts | Client-side timeout, a clear `llm_unavailable` error, no retry loop (P2.7) |
| Free-tier data retention | A public app sends user content to a provider that may reuse it | Documented, and the provider can be swapped through one setting |

4. When a limit is reached, the answer is a clear `429` with `Retry-After` and a machine-readable code, never a silent empty response.
5. Every future addition to the stack is checked against this section before it is adopted. If it cannot run for 0 €, it is not adopted.
