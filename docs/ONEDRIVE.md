## OneDrive / SharePoint Integration

This chapter describes how the project integrates with Microsoft Graph for OneDrive and SharePoint-backed drives.

### Architecture
- `app/integrations/onedrive_client.py`: thin client that wraps Graph calls and provides discovery, list/upload/download operations.
- `OAuthAuth`: implements OAuth2 client credentials (app-only) and in-memory token caching.
- `TestTokenAuth`: manual token provider for local testing.

### OneDrive vs SharePoint-backed drives
- Personal OneDrive (OneDrive for Business) typically uses `/me/drive` API paths.
- SharePoint-backed personal sites may require site-based discovery using the tenant hostname and site IDs.
- Discovery sequence (implemented in the client):
  1. `/me/drive`
  2. `/users/{upn}/drive`
  3. `/sites/{hostname}` → `/sites/{siteId}/drive`
  4. `/sites/{siteId}:/personal/{user_segment}:/drive` (personal site heuristics)
  5. `/drives` listing
  6. fallback to configured `MS_DRIVE_ID`

### Why OAuth app-only
- App-only auth provides centralized, non-interactive service access and is suitable for background workflows.
- It avoids needing per-user consent for server-side operations and simplifies multi-tenant automation.

### Troubleshooting
- 403 Forbidden:
  - Missing Application permission or missing admin consent. Ensure the app has Application permissions (Files.ReadWrite.All, Sites.Read.All) and grant admin consent.
- 404 Not Found during discovery:
  - Hostname may be incorrect. Verify `ONEDRIVE_HOSTNAME` in `.env`.
  - Try providing `MS_DRIVE_ID` explicitly in config to skip discovery.
- Token acquisition errors:
  - Verify `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT_ID`.
  - Confirm client secret hasn't expired and system clock is accurate.
# OneDrive Integration - Operational Document

## PURPOSE & SCOPE
- Purpose: Integrate with Microsoft Graph / OneDrive to upload and download attachments for tenant flows. Support both test tokens and production OAuth flows.
- Scope: Drive discovery, upload/download, listing, and enforcing base-path isolation.

## CURRENT STATUS
- Implemented:
  - Drive discovery with fallbacks: `/me/drive`, `/users/{upn}/drive`, site-based personal path `/sites/{hostname}:/personal/{user_segment}:/drive`, `/drives` scan, and configured `MS_DRIVE_ID` fallback.
  - Decision-level logging to `integration_events` (see migration `migrations/003_add_integration_events.sql`).
  - TestTokenAuth support for quick local testing using `MS_ACCESS_TOKEN`.
- In Progress:
  - Additional production OAuth flow integration tests (requires admin consent and client credentials).
- Blocked:
  - Some Graph API calls may return 400/403 depending on token permissions and tenant configuration. Work with tenant admin to ensure `Sites.Read.All`/`Files.ReadWrite.All` permissions when required.

## BACKEND IMPLEMENTATION
- Main code files:
  - `app/integrations/onedrive_api.py` - low-level Graph API wrapper and retry logic.
  - `app/integrations/onedrive_client.py` - drive discovery logic and high-level operations (list/upload/download).
  - `app/db/repositories/integration_event_repository.py` - persistence for `IntegrationEvent` records.
  - `migrations/003_add_integration_events.sql` - SQL to add `integration_events` table.

## AUTHENTICATION MODEL
- Test mode:
  - `TestTokenAuth`: set `MS_ACCESS_TOKEN` in environment; used for development/testing. No OAuth handshake.
- Production mode:
  - OAuth (Microsoft Identity / client credentials) is recommended: requires `client_id`, `client_secret`, tenant id, and required Graph scopes.

## REQUIRED ENVIRONMENT VARIABLES
- `MS_ACCESS_TOKEN` (optional for test mode)
- `MS_DRIVE_ID` (optional fallback drive id)
- `ONEDRIVE_HOSTNAME` (e.g., `tenant-my.sharepoint.com`)
- `ONEDRIVE_BASE_PATH` (required) - all operations must be constrained under this base path; enforced by code.

## EXTERNAL CONFIGURATION REQUIRED
- Microsoft admin may need to grant application permissions: `Sites.Read.All`, `Files.ReadWrite.All`, `User.Read.All` when using OAuth.

## ACTIVATION CHECKLIST (MODULE-SPECIFIC)
- [ ] Apply migration `migrations/003_add_integration_events.sql` to DB.
- [ ] Set env variables listed above.
- [ ] For production OAuth, provision an Azure AD app and set credentials in environment via secure secrets.
- [ ] Run discovery test using `scripts/onedrive_test.py` with the `MS_ACCESS_TOKEN` to confirm drive resolution.

## COMMON ERRORS & TROUBLESHOOTING
- Symptom: `/me/drive` returns 404
  - Cause: User's OneDrive is SharePoint-backed; need to attempt site-based discovery.
  - Action: Ensure `ONEDRIVE_HOSTNAME` is set and `MS_ACCESS_TOKEN` has permission to search sites, or provide `MS_DRIVE_ID` fallback.
- Symptom: Site personal lookup returns 400 or 403
  - Cause: Token lacks `Sites.Read.All` or site discovery is restricted.
  - Action: Request tenant admin to grant required Graph scopes or provide a drive id.
- Symptom: List/upload returns 404 after discovery
  - Cause: Drive id used may not contain expected `ONEDRIVE_BASE_PATH` or token cannot access that drive.
  - Action: Verify `ONEDRIVE_BASE_PATH` and token permissions; check `integration_events` records for discovery details.

## FUTURE IMPROVEMENTS / TODO
- Add full OAuth client credentials flow and automated token refresh.
- Add more unit/integration tests to cover SharePoint personal site cases.
- Add an admin UI for viewing `integration_events` and retrying discovery.

## Health Check Endpoint

- Path: `GET /admin/health/onedrive`
- Purpose: Verify server-side OAuth token acquisition and connectivity to the configured drive (`MS_DRIVE_ID`).
- Safe write: create+delete of `_healthcheck` when `ONEDRIVE_HEALTHCHECK_WRITE=true`.

Use this endpoint during activation to validate that the application credentials and drive configuration are correct.
