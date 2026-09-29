-- =============================================================
-- Migration 007: incident_sources (UFO Dossier v2)
-- Many-to-many between incidents and source_records.
-- Preserves existing incidents.source_file_id; adds provenance layer.
-- =============================================================

create table if not exists incident_sources (
  id uuid primary key default uuid_generate_v4(),
  incident_id uuid not null references incidents(id) on delete cascade,
  source_record_id uuid not null references source_records(id) on delete cascade,
  source_file_id uuid references source_files(id) on delete set null,
  role text not null default 'primary'
    check (role in ('primary', 'supporting', 'media', 'assessment', 'duplicate_of')),
  confidence text not null default 'exact'
    check (confidence in ('exact', 'normalized', 'manual', 'candidate')),
  notes text,
  created_at timestamptz not null default now(),
  unique (incident_id, source_record_id)
);

create index if not exists idx_incident_sources_incident on incident_sources(incident_id);
create index if not exists idx_incident_sources_record on incident_sources(source_record_id);
create index if not exists idx_incident_sources_file on incident_sources(source_file_id);

comment on table incident_sources is
  'v2 provenance link: incident ↔ official source_record (and optional source_file artifact)';
