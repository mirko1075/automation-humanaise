-- migrations/003_add_integration_events.sql
-- Adds a reusable integration_events table for integration-level logs

CREATE TABLE IF NOT EXISTS integration_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  integration varchar NOT NULL,
  event_type varchar NOT NULL,
  level varchar NOT NULL,
  message text NOT NULL,
  context jsonb,
  created_at timestamp without time zone DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_integration_events_integration ON integration_events(integration);
CREATE INDEX IF NOT EXISTS idx_integration_events_event_type ON integration_events(event_type);
CREATE INDEX IF NOT EXISTS idx_integration_events_created_at ON integration_events(created_at);
