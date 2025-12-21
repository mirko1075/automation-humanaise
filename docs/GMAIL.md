# Gmail Integration - Operational Document

## PURPOSE & SCOPE
- Purpose: Receive inbound email via Gmail Pub/Sub or webhook, persist raw payloads, normalize into a unified event, and route to tenant flows (preventivi, documenti, etc.).

## CURRENT STATUS
- Implemented:
  - Gmail webhook ingress (`app/api/ingress/gmail_webhook.py`) that validates Pub/Sub payloads and saves `RawEvent` records.
  - Normalizer (`app/core/normalizer.py`) converting MIME/email payloads into the unified normalized event structure.
  - Flow routing (`app/core/router.py`) to dispatch to `api/flows/*` handlers.
- In Progress:
  - Additional coverage for edge-case MIME parsing and encoding.

## BACKEND IMPLEMENTATION
- Main code files:
  - `app/api/ingress/gmail_webhook.py` - validates and saves raw payloads.
  - `app/core/normalizer.py` - produces `NormalizedEvent` objects used by flows.
  - `app/db/repositories/raw_event_repository.py` - persists raw payloads.

## AUTHENTICATION MODEL
- Gmail Pub/Sub: verify push subscriptions and signature/verify token if configured.

## REQUIRED ENVIRONMENT VARIABLES
- `GMAIL_PUBSUB_VERIFICATION_TOKEN` (if using push verification)

## EXTERNAL CONFIGURATION REQUIRED
- Configure Pub/Sub push subscription to point to `/webhooks/gmail` and set verification token.

## ACTIVATION CHECKLIST (MODULE-SPECIFIC)
- [ ] Configure Pub/Sub push subscription with correct endpoint and token.
- [ ] Ensure inbound email addresses are routed to the monitored Gmail account(s).
- [ ] Run sample email and verify `RawEvent` entry and that a `ProcessedEvent` is created by flows.

## COMMON ERRORS & TROUBLESHOOTING
- Symptom: Webhook returns 401/403
  - Action: Verify Pub/Sub verification token and webhook URL.
- Symptom: Normalizer fails for certain content-types
  - Action: Inspect `raw_events.payload` for MIME boundaries and encoding; update `app/core/normalizer.py` logic.

## FUTURE IMPROVEMENTS / TODO
- Add more robust MIME parsing and attachments extraction.
- Add metrics for inbound email rates and normalize failure rates.
