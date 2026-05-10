-- =============================================================
-- Migration 001: add media support (image_url, video_url)
-- Run against an existing ufodossier database to enable v1 media.
--
-- NOTE: We must DROP views before recreating them because adding
-- columns to incidents changes what i.* expands to, and Postgres
-- refuses CREATE OR REPLACE VIEW when column names/order shift.
-- =============================================================

-- 1. drop dependent views first (order matters: v_media_incidents depends on incidents too)
drop view if exists v_media_incidents;
drop view if exists v_incident_full;

-- 2. add new columns (idempotent)
alter table incidents add column if not exists image_url text;
alter table incidents add column if not exists video_url text;

-- 3. recreate the public view with the updated column set
create view v_incident_full as
select
  i.*,
  sf.url        as source_url,
  sf.filename   as source_filename,
  sf.agency     as source_agency,
  sf.storage_path as source_storage_path,
  sf.file_type  as source_file_type,
  sf.duration_seconds as source_duration_seconds,
  r.tranche_number
from incidents i
left join source_files sf on sf.id = i.source_file_id
left join releases r     on r.id  = sf.release_id;

-- 4. convenience view: all media-bearing incidents
create view v_media_incidents as
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
