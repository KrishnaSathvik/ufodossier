-- DESIGN ONLY. Do not apply this file to production in the V2 local milestone.
-- Ask telemetry columns for a later migration. The local app writes JSONL instead.

SELECT '010_rag_telemetry_DESIGN_ONLY: not applied' AS notice;

-- ALTER TABLE ask_log
--   ADD COLUMN IF NOT EXISTS provider text,
--   ADD COLUMN IF NOT EXISTS reasoning_effort text,
--   ADD COLUMN IF NOT EXISTS prompt_version text,
--   ADD COLUMN IF NOT EXISTS retrieval_version text,
--   ADD COLUMN IF NOT EXISTS retrieved_incident_ids uuid[],
--   ADD COLUMN IF NOT EXISTS citation_validation_status text,
--   ADD COLUMN IF NOT EXISTS input_tokens integer,
--   ADD COLUMN IF NOT EXISTS output_tokens integer,
--   ADD COLUMN IF NOT EXISTS reasoning_tokens integer,
--   ADD COLUMN IF NOT EXISTS retrieval_latency_ms integer,
--   ADD COLUMN IF NOT EXISTS generation_latency_ms integer,
--   ADD COLUMN IF NOT EXISTS latency_ms integer,
--   ADD COLUMN IF NOT EXISTS estimated_cost_usd numeric;
