# Activation Checklist

This document guides operators through enabling OneDrive/SharePoint integration with OAuth app-only.

1. Azure App Registration
   - Create an app registration in Azure AD.
   - Under "Certificates & secrets" create a client secret and copy the value.
   - Under "API permissions" add Application permissions (not delegated) depending on needs, e.g.:
     - Files.Read.All
     - Files.ReadWrite.All
     - Sites.Read.All
   - Click "Grant admin consent" for the tenant.

2. Environment Variables
   - In your deployment or `.env` set:
     - `ONEDRIVE_AUTH_MODE=app`
     - `MS_CLIENT_ID` (application ID)
     - `MS_CLIENT_SECRET` (client secret value)
     - `MS_TENANT_ID` (tenant GUID)
     - Optional: `MS_DRIVE_ID`, `ONEDRIVE_HOSTNAME`, `ONEDRIVE_BASE_PATH`

3. Startup validation
   - The app validates required OAuth env vars at startup when `ONEDRIVE_AUTH_MODE=app`.
   - If missing, startup will fail with an explanatory message.

4. Test the integration
   - Locally: run `PYTHONPATH=. python3 scripts/check_onedrive_auth.py` to validate token acquisition.
   - End-to-end: run `PYTHONPATH=. python3 scripts/onedrive_e2e_test.py` (this executes real Graph API calls).

5. Production considerations
   - Store `MS_CLIENT_SECRET` in a secrets manager (do not commit to git).
   - Consider using a shared token cache (Redis) for multi-worker deployments.

## Activation Checklist

This file lists the steps to activate the system in a new environment.

## Environment variables
- `DATABASE_URL` - Postgres connection string
- `REDIS_URL` - Optional for caching/queues
- `LOG_LEVEL` - INFO/DEBUG

## OneDrive (OAuth app-only - production)
- Ensure `ONEDRIVE_AUTH_MODE=app`
- Set: `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT_ID`
- Grant admin consent for scopes: `Sites.ReadWrite.All`, `Files.ReadWrite.All`

## OneDrive (Test token - development)
- Set: `ONEDRIVE_AUTH_MODE=test`
- Set: `MS_ACCESS_TOKEN` with a valid personal token for manual testing

## External services
- Gmail Pub/Sub credentials and subscription
- WhatsApp Cloud API app and webhook
- Slack webhook for alerts (`SLACK_WEBHOOK_URL`)

## Verification steps
1. Run migrations: apply SQL files in `migrations/`
2. Start service and check `/health` and `/ready`
3. Verify OneDrive auth:
   - For `app` mode: check logs for "OAuth token acquired"
   - For `test` mode: check that `TestTokenAuth` uses `MS_ACCESS_TOKEN`
4. Send a sample Gmail Pub/Sub message and follow the processing pipeline

## Troubleshooting
- If `/ready` fails, check DB connection and migrations
- For OneDrive token errors, inspect logs for auth error messages
