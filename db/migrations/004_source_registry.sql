-- =============================================================
-- Migration 004: Source Registry (UFO Dossier v2)
-- Official provider records independent of downloaded artifacts.
-- source_files remains for local/processed blobs.
--
-- Apply in Supabase SQL Editor after backup.
-- Idempotent where practical.
-- =============================================================

-- providers: pursue | aaro | nara (extensible)
create table if not exists source_records (
  id uuid primary key default uuid_generate_v4(),

  provider text not null check (provider in ('pursue', 'aaro', 'nara')),
  external_id text,                          -- official id when present (e.g. DOW-UAP-D114)
  identity_key text not null,                -- stable hash key for diffing

  release_number int,
  release_date date,
  release_label text,                        -- e.g. 'Release 06'

  title text,
  description text,

  agency text,
  agency_raw text,
  incident_date_hint text,
  incident_location_hint text,

  source_type text not null check (source_type in (
    'pdf', 'image', 'video', 'audio', 'webpage', 'other'
  )),

  original_url text,
  download_url text,
  thumbnail_url text,

  status text not null default 'active' check (status in (
    'active', 'deprecated', 'superseded', 'unavailable', 'pending'
  )),

  sha256 text,
  byte_size bigint,
  mime_type text,

  document_class text,                       -- filled by classify step
  contains_incidents boolean,

  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  downloaded_at timestamptz,
  verified_at timestamptz,

  metadata jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  unique (provider, identity_key)
);

create index if not exists idx_source_records_provider on source_records(provider);
create index if not exists idx_source_records_release on source_records(release_number);
create index if not exists idx_source_records_status on source_records(status);
create index if not exists idx_source_records_type on source_records(source_type);
create index if not exists idx_source_records_external on source_records(provider, external_id);
create index if not exists idx_source_records_url on source_records(original_url);

-- Link existing artifacts to registry rows (nullable for backfill)
alter table source_files
  add column if not exists source_record_id uuid references source_records(id) on delete set null;

create index if not exists idx_source_files_record on source_files(source_record_id);

-- Manifest snapshot provenance
create table if not exists manifest_snapshots (
  id uuid primary key default uuid_generate_v4(),
  provider text not null check (provider in ('pursue', 'aaro', 'nara')),
  snapshot_date date not null,
  release_number int,
  source_url text not null,
  storage_path text,                         -- local or storage path to immutable CSV
  sha256 text not null,
  record_count int not null default 0,
  diff_summary jsonb not null default '{}'::jsonb,
  captured_at timestamptz not null default now(),
  unique (provider, snapshot_date, sha256)
);

create index if not exists idx_manifest_snapshots_provider
  on manifest_snapshots(provider, snapshot_date desc);

-- Feature flags / corpus visibility helpers for v2 cutover
alter table releases
  add column if not exists provider text default 'pursue',
  add column if not exists release_label text,
  add column if not exists is_public boolean not null default true;

comment on table source_records is
  'v2 official source registry — one row per government record; artifacts live in source_files / media_assets';
