-- Add human-readable slug column for editorial URL routing
-- Format: {year}-{branch}-{first-3-words-kebab}-{4charhash}
-- Example: 2024-indopacom-football-shaped-object-a1b2

alter table incidents add column if not exists slug text unique;
create index if not exists idx_incidents_slug on incidents(slug);
