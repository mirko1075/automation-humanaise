# Activation Checklist

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
