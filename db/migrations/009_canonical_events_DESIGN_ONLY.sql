-- DESIGN DRAFT. Applied in production on 2026-09-29.
-- The runnable copy is db/migrations/011_canonical_and_ingestion.sql.
-- Do not execute this commented file.
-- Canonical identity layer for UFO Dossier (linker V1).
-- Extracted incidents remain immutable evidence units.

-- CREATE TABLE canonical_events (
--   id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
--   event_id text UNIQUE NOT NULL,
--   label text NOT NULL,
--   occurred_at date,
--   location_text text,
--   created_at timestamptz NOT NULL DEFAULT now()
-- );

-- CREATE TABLE event_members (
--   id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
--   event_id text NOT NULL REFERENCES canonical_events(event_id),
--   incident_case_id text NOT NULL,
--   source_filename text NOT NULL,
--   role text NOT NULL DEFAULT 'observation',
--   episode_id text,
--   UNIQUE (event_id, incident_case_id)
-- );

-- CREATE TABLE event_sources (
--   id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
--   event_id text NOT NULL REFERENCES canonical_events(event_id),
--   source_filename text NOT NULL,
--   relationship text NOT NULL,
--   document_class text,
--   UNIQUE (event_id, source_filename, relationship)
-- );

-- CREATE TABLE event_series (
--   id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
--   series_id text UNIQUE NOT NULL,
--   label text NOT NULL,
--   created_at timestamptz NOT NULL DEFAULT now()
-- );

-- CREATE TABLE series_events (
--   series_id text NOT NULL REFERENCES event_series(series_id),
--   event_id text NOT NULL REFERENCES canonical_events(event_id),
--   PRIMARY KEY (series_id, event_id)
-- );

-- CREATE TABLE link_decisions (
--   id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
--   decision_id text UNIQUE NOT NULL,
--   relationship text NOT NULL,
--   status text NOT NULL,
--   left_ref text NOT NULL,
--   right_ref text NOT NULL,
--   evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
--   score_band text,
--   auto_merged boolean NOT NULL DEFAULT false,
--   incidents_rewritten boolean NOT NULL DEFAULT false,
--   created_at timestamptz NOT NULL DEFAULT now()
-- );

SELECT '009_canonical_events_DESIGN_ONLY: draft only; production copy is 011' AS notice;
