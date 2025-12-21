# WhatsApp Integration - Operational Document

## PURPOSE & SCOPE
- Purpose: Send notifications and receive messages via WhatsApp for tenant flows (e.g., preventivi confirmations, equipment alerts).
- Scope: Webhook receiving messages, sending messages via provider API, handling media attachments.

## CURRENT STATUS
- Implemented:
  - Webhook ingress endpoint (`app/api/ingress/whatsapp_webhook.py`) to receive and validate messages.
  - Outbound notifications client (`app/integrations/whatsapp_api.py`) supporting send and media operations.
- In Progress:
  - Operational verification across tenant phone numbers and templates.

## BACKEND IMPLEMENTATION
- Main code files:
  - `app/api/ingress/whatsapp_webhook.py` - webhook receiver and validator.
  - `app/integrations/whatsapp_api.py` - client for sending messages and media.
  - `app/api/flows/attrezzature_v1.py` - flow that reacts to equipment-related messages.

## AUTHENTICATION MODEL
- Test mode:
  - Use test API token in `WHATSAPP_API_TOKEN` environment variable for development providers that accept token-only authentication.
- Production mode:
  - Use provider credentials (API token, app secret) and configure webhook verification token on provider dashboard.

## REQUIRED ENVIRONMENT VARIABLES
- `WHATSAPP_API_TOKEN`
- `WHATSAPP_WEBHOOK_TOKEN` (for validating incoming webhooks)

## EXTERNAL CONFIGURATION REQUIRED
- Configure webhook URL in WhatsApp provider dashboard with the `WHATSAPP_WEBHOOK_TOKEN`.

## ACTIVATION CHECKLIST (MODULE-SPECIFIC)
- [ ] Set `WHATSAPP_API_TOKEN` and `WHATSAPP_WEBHOOK_TOKEN`.
- [ ] Configure provider webhook to point at `/webhooks/whatsapp` route and verify.
- [ ] Send test message and verify the `attrezzature_v1` flow triggers.

## COMMON ERRORS & TROUBLESHOOTING
- Symptom: Webhook validation fails
  - Action: Verify webhook token matches `WHATSAPP_WEBHOOK_TOKEN` and request signature if applicable.
- Symptom: Outbound messages not delivered
  - Action: Check provider API logs, verify phone numbers and templates, ensure `WHATSAPP_API_TOKEN` is valid.

## FUTURE IMPROVEMENTS / TODO
- Add message templating and delivery receipts persistence.
- Add retry queue for failed outbound messages using Redis/Celery.
