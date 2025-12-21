# OneDrive Discovery Logs

This document describes how OneDrive discovery decision-level events are stored and how to query them.

## Data model

Table: `integration_events`

Fields:
- `id` (UUID) primary key
- `integration` (string) e.g. `onedrive`
- `event_type` (string) one of: `discovery_attempt`, `discovery_success`, `discovery_fallback`, `discovery_failed`
- `level` (string) e.g. `INFO`, `WARN`, `ERROR`
- `message` (string) human-readable
- `context` (JSON) compact technical details (hostname, drive_id, user_segment)
- `created_at` (timestamp)

## Admin endpoint

GET `/admin/integrations/onedrive/logs`

Query params:
- `level` (optional) filter by `INFO|WARN|ERROR`
- `event_type` (optional) filter by event type
- `since` (optional) ISO timestamp (inclusive)
- `limit` (optional) default `50`
- `offset` (optional) default `0`

Response example:

```json
{
  "status": "success",
  "data": [
    {
      "id": "...",
      "created_at": "2025-12-13T09:41:22Z",
      "level": "WARN",
      "event_type": "discovery_fallback",
      "message": "Fallback to site-based discovery",
      "context": { "hostname": "netorg17930091-my.sharepoint.com" }
    }
  ]
}
```

## Notes
- Only decision-level events are persisted. No tokens, headers or full request bodies are stored.
- The table is generic and can be reused for other integrations in the future (gmail, whatsapp, etc.).

## Postman
- A request `OneDrive Discovery Logs` was added to `postman_collection.json` under the Monitoring group.
