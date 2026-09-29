-- =============================================================
-- Migration 005: media_assets (UFO Dossier v2)
-- First-class media linked to source_records.
-- incidents.image_url / video_url remain for back-compat until cutover.
-- =============================================================

create table if not exists media_assets (
  id uuid primary key default uuid_generate_v4(),
  source_record_id uuid references source_records(id) on delete set null,
  source_file_id uuid references source_files(id) on delete set null,

  media_type text not null check (media_type in ('image', 'video', 'audio')),
  original_url text,
  storage_url text,
  thumbnail_url text,

  mime_type text,
  duration_seconds numeric,
  width int,
  height int,
  sha256 text,
  byte_size bigint,

  transcript text,
  transcript_model text,
  transcript_segments jsonb,                 -- [{start_seconds, end_seconds, text, speaker?}]

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_media_assets_record on media_assets(source_record_id);
create index if not exists idx_media_assets_type on media_assets(media_type);
create index if not exists idx_media_assets_file on media_assets(source_file_id);

-- Many-to-many: incident ↔ media
create table if not exists incident_media (
  incident_id uuid not null references incidents(id) on delete cascade,
  media_asset_id uuid not null references media_assets(id) on delete cascade,
  role text default 'primary',
  primary key (incident_id, media_asset_id)
);

create or replace view v_media_assets_public as
select
  m.*,
  sr.provider,
  sr.external_id,
  sr.title as source_title,
  sr.release_number,
  sr.agency
from media_assets m
left join source_records sr on sr.id = m.source_record_id
where sr.status is null or sr.status = 'active';
