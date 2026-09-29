-- Applied in the Supabase SQL editor on 2026-09-29.
-- Idempotent record of that change. Do not run it again against production
-- unless you are recreating an empty database that already has migration 004.
-- Ask telemetry (010) is intentionally not included.

alter table source_records
  add column if not exists storage_status text
    check (storage_status in ('pending', 'cached_local', 'uploaded', 'failed', 'skipped')),
  add column if not exists ingestion_state text
    check (ingestion_state in (
      'discovered', 'classified', 'source_only', 'ocr_ready',
      'extracted', 'validated', 'embedded', 'flagged_review'
    )),
  add column if not exists classification_confidence text,
  add column if not exists classification_reason text,
  add column if not exists classified_at timestamptz;

create table if not exists canonical_events (
  id uuid primary key default gen_random_uuid(),
  event_id text unique not null,
  label text not null,
  occurred_at date,
  location_text text,
  created_at timestamptz not null default now()
);

create table if not exists event_members (
  id uuid primary key default gen_random_uuid(),
  event_id text not null references canonical_events(event_id),
  incident_case_id text not null,
  source_filename text not null,
  role text not null default 'observation',
  episode_id text,
  unique (event_id, incident_case_id)
);

create table if not exists event_sources (
  id uuid primary key default gen_random_uuid(),
  event_id text not null references canonical_events(event_id),
  source_filename text not null,
  relationship text not null,
  document_class text,
  unique (event_id, source_filename, relationship)
);

create table if not exists event_series (
  id uuid primary key default gen_random_uuid(),
  series_id text unique not null,
  label text not null,
  created_at timestamptz not null default now()
);

create table if not exists series_events (
  series_id text not null references event_series(series_id),
  event_id text not null references canonical_events(event_id),
  primary key (series_id, event_id)
);

create table if not exists link_decisions (
  id uuid primary key default gen_random_uuid(),
  decision_id text unique not null,
  relationship text not null,
  status text not null,
  left_ref text not null,
  right_ref text not null,
  evidence jsonb not null default '[]'::jsonb,
  score_band text,
  auto_merged boolean not null default false,
  incidents_rewritten boolean not null default false,
  created_at timestamptz not null default now()
);
