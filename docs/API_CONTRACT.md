# API Contract v1

> **This contract is shared with the frontend repository and describes the TARGET state. Both repositories must keep an identical copy. Any change must be made in both.**

Contract version: `v1`
Status: partially implemented. All endpoints in §3 are live, including SSE streaming; throttling and the global daily cap (§9) and the provider circuit breaker are planned. The currently deployed API is documented in [`docs/api/api-documentation.md`](api/api-documentation.md).

## 1. Product

- Product name: **Zenith AI**. The name ChatGPT / chatgpt must not appear anywhere in the code, the documentation, or the payloads.
- The product is 100% free and open to everyone: no credits, no premium tier, no payment.
- Target infrastructure cost: **0 €**. Only free technologies and free services are allowed.

## 2. Environments

| | Value |
|---|---|
| Frontend (dev) | `http://localhost:5173` |
| Backend (dev) | `http://localhost:8000` |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` |
| API base path | `/api/v1/` |
| Swagger UI | `/api/v1/docs/` |
| ReDoc | `/api/v1/redoc/` |
| OpenAPI schema | `/api/v1/schema/` |

## 3. Endpoints

Status legend: **Implemented** = available today, **Planned** = described by this contract, not built yet.

| Method | Path | Auth | Status | Currently served at |
|---|---|---|---|---|
| POST | `/auth/register/` | No | Implemented | `POST /api/v1/auth/register/` |
| POST | `/auth/token/` | No | Implemented | `POST /api/v1/auth/token/` |
| POST | `/auth/token/refresh/` | No | Implemented | `POST /api/v1/auth/token/refresh/` |
| POST | `/auth/logout/` | No | Implemented | `POST /api/v1/auth/logout/` |
| GET | `/auth/profile/` | Yes | Implemented | `GET /api/v1/auth/profile/` |
| PATCH | `/auth/profile/` | Yes | Implemented | `PATCH /api/v1/auth/profile/` |
| GET | `/conversations/` | Yes | Implemented | `GET /api/v1/chat/conversations/` (paginated, page size 20) |
| POST | `/conversations/` | Yes | Implemented | `POST /api/v1/chat/conversations/` |
| GET | `/conversations/{uuid}/` | Yes | Implemented | `GET /api/v1/chat/conversations/{uuid}/` |
| PATCH | `/conversations/{uuid}/` | Yes | Implemented | `PATCH /api/v1/chat/conversations/{uuid}/` |
| DELETE | `/conversations/{uuid}/` | Yes | Implemented | `DELETE /api/v1/chat/conversations/{uuid}/` |
| GET | `/conversations/{uuid}/messages/` | Yes | Implemented | `GET /api/v1/chat/conversations/{uuid}/messages/` |
| POST | `/conversations/{uuid}/messages/` | Yes | Implemented | `POST /api/v1/chat/conversations/{uuid}/messages/` |
| POST | `/conversations/{uuid}/messages/stream/` | Yes | Implemented | `POST /api/v1/chat/conversations/{uuid}/messages/stream/` (SSE) |
| GET | `/health/` | No | Implemented | `GET /api/v1/health/` |

### 3.1 Method set

- `/auth/profile/`: only `GET` and `PATCH`. `PUT` is not part of the contract.
- `/conversations/{uuid}/`: only `GET`, `PATCH` and `DELETE`. `PUT` is not part of the contract.
- `PUT` and `PATCH` on conversations are limited to the `title` field.

### 3.2 Conversation creation

Creating a conversation explicitly is supported. Sending a message to a conversation that does not exist yet is **not** part of the contract: the frontend creates the conversation first, then posts the first message.

## 4. Public identifiers

- All public ids are **UUIDs**, exposed as strings. Integer primary keys are internal only.
- Conversations and messages returned by the API always carry their `uuid`.

## 5. Pagination

All list endpoints are paginated with the standard DRF envelope and a page size of **20**.

```json
{
  "count": 42,
  "next": "http://localhost:8000/api/v1/conversations/?page=2",
  "previous": null,
  "results": []
}
```

The frontend reads `results`, and uses `count`, `next` and `previous` for navigation only.

## 6. Authentication

- JWT is carried in the request body as JSON, never in a query string or a cookie.
- Access token lifetime: **15 minutes**.
- Refresh token lifetime: **7 days**, with rotation, and the rotated token is blacklisted.
- Header: `Authorization: Bearer <token>`.
- Logout blacklists the refresh token presented in the body.

| Endpoint | Request | Response |
|---|---|---|
| `POST /auth/register/` | `{"email", "username", "password", "password2"}` | `201` user object |
| `POST /auth/token/` | `{"email", "password"}` | `{"access", "refresh"}` |
| `POST /auth/token/refresh/` | `{"refresh"}` | `{"access", "refresh"}` |
| `POST /auth/logout/` | `{"refresh"}` | `204` |
| `GET /auth/profile/` | — | `200` user object |
| `PATCH /auth/profile/` | partial user object | `200` user object |

## 7. Streaming

Streaming is **SSE only** (`text/event-stream`). WebSocket is not used anywhere.

| Event | Payload |
|---|---|
| `token` | `data: {"content":"<fragment>"}` |
| `done` | `data: {"message_id":"<uuid>","conversation_id":"<uuid>"}` |
| `error` | `data: {"code":"<code>","message":"<text>"}` |

A non-streaming message post returns the complete assistant message.

## 8. Error format

Every error response, without exception, uses this envelope:

```json
{
  "error": {
    "code": "<code>",
    "message": "<text>",
    "details": {}
  }
}
```

| Code | HTTP | Meaning |
|---|---|---|
| `validation_error` | 400 | Invalid payload |
| `unauthorized` | 401 | Missing, invalid or expired token |
| `forbidden` | 403 | Authenticated but not allowed |
| `not_found` | 404 | Unknown resource, or not owned by the caller |
| `method_not_allowed` | 405 | HTTP method not allowed on this endpoint |
| `rate_limited` | 429 | Per-IP or per-user throttling |
| `quota_exhausted` | 429 | Global daily cap reached |
| `llm_unavailable` | 503 | Provider unreachable, errored or rate limited; a provider `429` is included here, with a `Retry-After` header when the provider supplies one |
| `server_error` | 500 | Unexpected failure |

A resource that exists but belongs to someone else returns `404 not_found`, never `403`, so that ids cannot be probed.

## 9. Usage limits

- Throttling per IP and per user.
- A global daily cap shared by all users.
- Exceeding a limit returns `429` with a `Retry-After` header and the code `rate_limited` or `quota_exhausted`.
- There are no credits and no billing state on the user.

## 10. LLM

- One free provider key, server-side only, read from the environment.
- The key is accessed through a single provider interface. No API key is ever stored per user.
- Users never send their own provider key.

## 11. Environment variables

Backend:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django signing key |
| `DEBUG` | `True` in dev, `False` in prod |
| `ALLOWED_HOSTS` | Comma-separated host list |
| `DATABASE_URL` or `DB_*` | Database connection |
| `CORS_ALLOWED_ORIGINS` | Comma-separated frontend origins |
| `LLM_PROVIDER` | Active provider (`gemini`, `groq`), `LLM_*` are the only LLM settings |
| `LLM_API_KEY` | Free provider key |
| `LLM_MODEL` | Model id |
| `LLM_FALLBACK_PROVIDER` | Second provider used automatically when the primary is rate limited or unavailable |
| `LLM_FALLBACK_API_KEY` | Key of the fallback provider |
| `LLM_FALLBACK_MODEL` | Model id of the fallback provider |
| `LLM_PROMPT_BUDGET` | Token budget for the history sent with each request (default `4000`) |

Frontend:

| Variable | Value |
|---|---|
| `VITE_API_URL` | `http://localhost:8000/api/v1` |

`VITE_WS_URL` does not exist: streaming is SSE, not WebSocket.

## 12. Versioning and deprecation

- The contract version is part of the URL: `v1` is the `/api/v1/` base path. A change that keeps `v1` keeps the same base path.
- A change is **non-breaking** when it only adds a resource, an endpoint, an optional field or a new error code, and never removes, renames or reinterprets something that exists. Non-breaking changes stay on the current version.
- Any other change is **breaking**: removing or renaming a field or endpoint, changing a payload shape, changing a status code or an error code, or changing the meaning of an existing value. A breaking change requires a new major version served at `/api/v2/`, and the previous version keeps serving unmodified for the announced deprecation period.
- Every version change is announced in the changelog before it ships, and the deprecation of the previous version is recorded there.
- This contract is copied into both the backend and the frontend repository: a version change updates both copies in the same release, and both repositories state the same contract version.
