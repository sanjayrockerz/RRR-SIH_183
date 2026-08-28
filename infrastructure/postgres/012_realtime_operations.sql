ALTER TABLE realtime_events ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE realtime_events ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ;
ALTER TABLE realtime_events ADD COLUMN IF NOT EXISTS dead_lettered_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_realtime_events_retry ON realtime_events(processing_status,next_attempt_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_processing_attempt_number ON processing_attempts(event_id,attempt_number);
