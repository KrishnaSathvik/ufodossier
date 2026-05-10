-- =============================================================
-- Migration 003: add cover_image_url to source_files & incidents
-- Rendered PDF page-1 JPEG for visual coverage.
--
-- NOTE: We must DROP views before recreating them because adding
-- columns changes what i.* expands to, and Postgres refuses
-- CREATE OR REPLACE VIEW when column names/order shift.
-- =============================================================

-- 1. drop dependent views first (order matters)
DROP VIEW IF EXISTS v_media_incidents;
DROP VIEW IF EXISTS v_incident_full;

-- 2. add new columns (idempotent)
ALTER TABLE source_files ADD COLUMN IF NOT EXISTS cover_image_url text;
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS cover_image_url text;

-- 3. recreate the public view with cover_image_url
CREATE VIEW v_incident_full AS
SELECT
  i.*,
  sf.url        AS source_url,
  sf.filename   AS source_filename,
  sf.agency     AS source_agency,
  sf.storage_path AS source_storage_path,
  sf.file_type  AS source_file_type,
  sf.duration_seconds AS source_duration_seconds,
  sf.cover_image_url AS source_cover_image_url,
  r.tranche_number
FROM incidents i
LEFT JOIN source_files sf ON sf.id = i.source_file_id
LEFT JOIN releases r     ON r.id  = sf.release_id;

-- 4. recreate media view (unchanged logic)
CREATE VIEW v_media_incidents AS
SELECT
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
  sf.url        AS source_url,
  sf.filename   AS source_filename,
  sf.file_type  AS source_file_type,
  sf.agency     AS source_agency
FROM incidents i
LEFT JOIN source_files sf ON sf.id = i.source_file_id
WHERE (i.image_url IS NOT NULL OR i.video_url IS NOT NULL)
  AND NOT i.flagged;
