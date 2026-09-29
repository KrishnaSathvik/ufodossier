-- =============================================================
-- Migration 006: public stats exclude flagged duplicates
-- Aligns homepage counts with curated corpus (380 unflagged today).
-- =============================================================

create or replace view v_stats as
select
  (select count(*) from incidents where not flagged) as incident_count,
  (select count(*) from source_files where file_type = 'pdf') as source_file_count,
  (select count(*) from incidents where resolution_status = 'unresolved' and not flagged) as unresolved_count,
  (select count(distinct country) from incidents where country is not null and not flagged) as country_count,
  (select min(occurred_at) from incidents where not flagged) as earliest,
  (select max(occurred_at) from incidents where not flagged) as latest,
  (select max(captured_at) from releases) as last_tranche,
  (select count(*) from incidents where flagged) as flagged_count,
  (select count(distinct release_number) from source_records where status = 'active') as release_count;
