# Role-Based Access Control Model

## Authentication

WorkTicket uses Clerk for authentication. JWT tokens are issued by Clerk and verified on every API request. Each token contains:

- `sub` — User ID
- `company_id` — Tenant identifier
- `token_version` — Enables instant deactivation

## Authorization Flow

```
Request → Clerk JWT → Token Version Check → Company ID Extraction → Permission Check → Authorized
```

1. **JWT Verification** — Clerk SDK validates the token signature, issuer, and audience
2. **Token Version Check** — `app/auth/authorize.py` compares the token's `token_version` against the user's current version. Deactivated users get a version bump that invalidates all active tokens
3. **company_id Scoping** — The tenant context is set from the JWT claim
4. **Permission Check** — Endpoint-level authorization via `app/auth/dependencies.py`

## Role Model

WorkTicket currently uses a simplified role model:

| Role | Scope | Capabilities |
|---|---|---|
| `admin` | Company | Full access: manage users, billing, company settings |
| `technician` | Company | Job CRUD, media upload, estimate review, quote approval |
| `office` | Company | Customer management, reporting, billing read |

Roles are enforced via the `require_role()` dependency in `app/auth/dependencies.py`.

## Endpoint Authorization

All protected endpoints require:
1. A valid JWT (`Depends(verify_token)`)
2. A valid token version (`Depends(verify_token_version)`)
3. Appropriate role (`Depends(require_role("admin"))` — optional per endpoint)

## Token Deactivation

When a user is deactivated, their `token_version` is incremented. This immediately invalidates:

- All active API sessions
- All active WebSocket connections
- All cached auth data

See `tests/test_token_version.py` for verification.

## Verified Authorization Paths

- Deactivated user token rejected (`test_deactivated_user_old_token_rejected`)
- WebSocket token version verified (`test_websocket_verifies_token_version`)
- Unauthenticated requests blocked (`test_unauthenticated_requests_rejected`)
- API permission checks on all endpoints
