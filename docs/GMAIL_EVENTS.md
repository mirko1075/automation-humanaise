# Gmail Events Admin Endpoint

This endpoint allows admins to list Gmail raw events stored in the `raw_events` table.

Endpoint: GET `/admin/monitoring/gmail_events`

Query parameters:
- `processed` (optional): `true` to list accepted/processed events, `false` to list discarded.
- `event_type` (optional): filter by event_type in the payload.
- `start_date` / `end_date` (optional): ISO timestamps to filter by created_at.
- `limit`, `offset` (optional): pagination.

Example:

```
curl 'http://localhost:9100/admin/monitoring/gmail_events?processed=true&limit=50'
```

Response: paginated list of events with `id`, `tenant_id`, `processed`, `payload`, `created_at`.

Notes:
- The payload field contains the raw Gmail webhook payload saved at ingestion.
- Use this endpoint to debug which messages were processed or discarded by flows.
