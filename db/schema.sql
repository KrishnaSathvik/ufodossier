-- =============================================================
-- UFODOSSIER // database schema
-- Supabase (Postgres + pgvector + Storage)
-- =============================================================

-- enable extensions
create extension if not exists "uuid-ossp";
create extension if not exists "vector";
create extension if not exists "pg_trgm";

-- =============================================================
-- releases: each war.gov tranche
-- =============================================================
create table if not exists releases (
  id uuid primary key default uuid_generate_v4(),
  tranche_number int not null,
  captured_at timestamptz not null default now(),
  released_at timestamptz,                   -- when war.gov posted it
  file_count int not null default 0,
  incident_count int not null default 0,
  notes text,
  unique (tranche_number)
);

-- =============================================================
-- source_files: every PDF, video, image we pulled from war.gov
-- =============================================================
create table if not exists source_files (
  id uuid primary key default uuid_generate_v4(),
  release_id uuid references releases(id) on delete set null,
  url text not null unique,                  -- canonical war.gov URL
  filename text not null,
  file_type text not null,                   -- pdf | mp4 | jpg | png
  agency text,                               -- DoD | FBI | NASA | DOS | etc
  released_at timestamptz,
  sha256 text not null,
  storage_path text,                         -- supabase storage object path
  byte_size bigint,
  page_count int,                            -- for pdfs
  duration_seconds int,                      -- for videos
  ocr_text text,                             -- full extracted text for pdfs
  transcript text,                           -- whisper output for videos
  ocr_method text,                           -- 'pypdf' | 'tesseract'
  cover_image_url text,                      -- rendered page-1 JPEG
  processed_at timestamptz,
  processing_error text,
  created_at timestamptz not null default now()
);

create index if not exists idx_source_files_release on source_files(release_id);
create index if not exists idx_source_files_agency on source_files(agency);
create index if not exists idx_source_files_text on source_files using gin (ocr_text gin_trgm_ops);

-- =============================================================
-- incidents: structured rows extracted by haiku
-- =============================================================
create table if not exists incidents (
  id uuid primary key default uuid_generate_v4(),
  case_id text unique,                       -- our slug e.g. '2024-IPC-0412'

  source_file_id uuid not null references source_files(id) on delete cascade,
  source_page int,                           -- which pdf page (if applicable)

  -- temporal
  occurred_at date,
  occurred_at_precision text check (occurred_at_precision in ('day','month','year','decade','unknown')),
  occurred_at_text text,                     -- raw string from source

  -- spatial
  location_text text,
  country text,
  region text,                               -- state, sea, etc
  lat numeric(9,6),
  lon numeric(9,6),
  geocode_method text,                       -- 'nominatim' | 'manual' | null
  geocode_confidence text,                   -- 'high' | 'med' | 'low'

  -- attribution
  branch text,                               -- USAF, USN, NASA, FBI, DOS, etc
  reporting_unit text,                       -- INDOPACOM, NORTHCOM, etc

  -- the encounter
  sensor_types text[] not null default '{}', -- ['infrared','radar','eyewitness','photo']
  duration_seconds int,
  altitude_feet int,
  shape_description text,
  size_description text,

  -- content
  title text not null,                       -- short headline for tables
  summary text not null,                     -- 2-3 sentence factual summary
  raw_excerpt text not null,                 -- verbatim text from source supporting summary

  -- resolution
  resolution_status text not null check (resolution_status in ('unresolved','identified','insufficient_data')),
  resolution_notes text,

  -- media
  image_url text,                          -- associated image (war.gov URL or storage)
  video_url text,                          -- associated video (war.gov URL or storage)
  cover_image_url text,                    -- rendered PDF page-1 JPEG

  -- search
  embedding vector(1536),

  -- audit
  extracted_at timestamptz not null default now(),
  extraction_model text,                     -- 'claude-haiku-4-5'
  extraction_version text,                   -- prompt version
  human_reviewed boolean not null default false,
  flagged boolean not null default false,
  flag_reason text
);

create index if not exists idx_incidents_source on incidents(source_file_id);
create index if not exists idx_incidents_occurred on incidents(occurred_at);
create index if not exists idx_incidents_status on incidents(resolution_status);
create index if not exists idx_incidents_branch on incidents(branch);
create index if not exists idx_incidents_country on incidents(country);
create index if not exists idx_incidents_sensors on incidents using gin (sensor_types);
create index if not exists idx_incidents_summary on incidents using gin (summary gin_trgm_ops);
create index if not exists idx_incidents_embedding on incidents using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- =============================================================
-- entities: people, units, aircraft, places mentioned across incidents
-- (lightweight — we extract names and link them, no deep NER)
-- =============================================================
create table if not exists entities (
  id uuid primary key default uuid_generate_v4(),
  kind text not null check (kind in ('person','unit','aircraft','sensor','location','program')),
  name text not null,
  normalized_name text not null,
  description text,
  mention_count int not null default 0,
  unique (kind, normalized_name)
);

create table if not exists incident_entities (
  incident_id uuid not null references incidents(id) on delete cascade,
  entity_id uuid not null references entities(id) on delete cascade,
  role text,
  primary key (incident_id, entity_id)
);

-- =============================================================
-- ask_log: every question asked to /ask, for permalinks + analytics
-- =============================================================
create table if not exists ask_log (
  id uuid primary key default uuid_generate_v4(),
  slug text unique,                          -- short permalink id
  question text not null,
  answer text,
  cited_incident_ids uuid[],
  model text,                                -- 'claude-sonnet-4-7'
  asked_at timestamptz not null default now(),
  user_agent text,
  ip_hash text                               -- sha256(ip + salt) for rate limiting
);

create index if not exists idx_ask_slug on ask_log(slug);
create index if not exists idx_ask_asked on ask_log(asked_at desc);

-- =============================================================
-- views for the public site
-- =============================================================
create or replace view v_incident_full as
select
  i.*,
  sf.url as source_url,
  sf.filename as source_filename,
  sf.agency as source_agency,
  sf.storage_path as source_storage_path,
  sf.file_type as source_file_type,
  sf.duration_seconds as source_duration_seconds,
  sf.cover_image_url as source_cover_image_url,
  r.tranche_number
from incidents i
left join source_files sf on sf.id = i.source_file_id
left join releases r on r.id = sf.release_id;

-- convenience view: all media-bearing incidents (for /images and /videos pages)
create or replace view v_media_incidents as
select
  i.id,
  i.case_id,
  i.title,
  i.summary,
  i.occurred_at,
  i.location_text,
  i.branch,
  i.resolution_status,
  i.image_url,
  i.video_url,
  sf.url        as source_url,
  sf.filename   as source_filename,
  sf.file_type  as source_file_type,
  sf.agency     as source_agency
from incidents i
left join source_files sf on sf.id = i.source_file_id
where (i.image_url is not null or i.video_url is not null)
  and not i.flagged;

create or replace view v_stats as
select
  (select count(*) from incidents) as incident_count,
  (select count(*) from source_files) as source_file_count,
  (select count(*) from incidents where resolution_status = 'unresolved') as unresolved_count,
  (select count(distinct country) from incidents where country is not null) as country_count,
  (select min(occurred_at) from incidents) as earliest,
  (select max(occurred_at) from incidents) as latest,
  (select max(captured_at) from releases) as last_tranche;

-- =============================================================
-- vector search rpc for /ask endpoint
-- =============================================================
create or replace function match_incidents(
  query_embedding vector(1536),
  match_threshold float default 0.5,
  match_count int default 10
)
returns table (
  id uuid,
  case_id text,
  title text,
  summary text,
  raw_excerpt text,
  occurred_at date,
  location_text text,
  branch text,
  resolution_status text,
  similarity float
)
language sql stable
as $$
  select
    incidents.id,
    incidents.case_id,
    incidents.title,
    incidents.summary,
    incidents.raw_excerpt,
    incidents.occurred_at,
    incidents.location_text,
    incidents.branch,
    incidents.resolution_status,
    1 - (incidents.embedding <=> query_embedding) as similarity
  from incidents
  where 1 - (incidents.embedding <=> query_embedding) > match_threshold
    and not flagged
  order by incidents.embedding <=> query_embedding
  limit match_count;
$$;

-- =============================================================
-- row-level security: read-only for anon
-- =============================================================
alter table incidents enable row level security;
alter table source_files enable row level security;
alter table releases enable row level security;
alter table entities enable row level security;
alter table incident_entities enable row level security;
alter table ask_log enable row level security;

create policy "public read incidents" on incidents for select using (not flagged);
create policy "public read source_files" on source_files for select using (true);
create policy "public read releases" on releases for select using (true);
create policy "public read entities" on entities for select using (true);
create policy "public read incident_entities" on incident_entities for select using (true);
create policy "public read ask_log" on ask_log for select using (true);

-- ===== Redesign migration: human-readable incident URLs =====
alter table incidents add column if not exists slug text unique;
create index if not exists idx_incidents_slug on incidents(slug);

-- ===== Collections migration =====
create table if not exists collections (
  id uuid primary key default uuid_generate_v4(),
  slug text unique not null,
  title text not null,
  standfirst text not null,
  intro_md text,
  sort_order int not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists collection_incidents (
  collection_id uuid not null references collections(id) on delete cascade,
  incident_id uuid not null references incidents(id) on delete cascade,
  sort_order int not null default 0,
  primary key (collection_id, incident_id)
);

alter table collections enable row level security;
alter table collection_incidents enable row level security;
create policy "public read collections" on collections for select using (true);
create policy "public read collection_incidents" on collection_incidents for select using (true);
