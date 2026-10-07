# Changelog

Notable API and behavior changes are recorded here, following the versioning and deprecation policy in [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) section 12. Every breaking change announces a new contract version here before it ships.

## Contract v1 — 2026-10-07

The API surface moved to the shared contract described in [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md). The changelog starts with this baseline.

- All endpoints are served under the `/api/v1/` base path. The legacy `/api/auth/` and `/api/chat/` routes are removed and return `404`.
- Every error response uses the shared envelope `{"error": {"code", "message", "details"}}`.
- Conversations and messages are identified by `uuid` strings.
- Messages are sent to `POST /api/v1/chat/conversations/{uuid}/messages/`. A conversation is never created implicitly by a message.
- List endpoints paginate with a page size of 20.
- The profile is `GET`/`PATCH` only; `PUT` returns `405`.
- Added `POST /api/v1/auth/logout/` and `GET /api/v1/health/`.
- The OpenAPI schema and interactive documentation are served at `/api/v1/schema/`, `/api/v1/docs/` and `/api/v1/redoc/`.

Deprecations:

- None currently active.