# UFO Dossier v2 — Data Migration Notes

## Blocking prerequisite

1. Confirm Supabase backup (Dashboard → Database → Backups, or `pg_dump`).
2. Do **not** run R02–R06 downloads until backup is verified.

## Schema apply order

```text
004_source_registry.sql
005_media_assets.sql
006_public_stats_exclude_flagged.sql
```

After 006, public `v_stats.incident_count` drops from 480 → **380** (excludes `duplicate_excerpt` flags).

## Manifest discovery

```bash
# Prefer official (requires curl_cffi for war.gov Akamai):
pip install curl_cffi
python -m pipeline.discover --provider pursue --snapshot-date 2026-09-18

# If official 403s in this environment:
python -m pipeline.discover --provider pursue --snapshot-date 2026-09-18 --allow-community-fallback
```

Community fallback is for bootstrap only. Re-run against war.gov before production cutover and compare `manifest.sha256`.

## Diffing

```bash
python -m pipeline.diff_manifest \
  --prev pipeline/snapshots/pursue/2026-08-07 \
  --curr pipeline/snapshots/pursue/2026-09-18 \
  --write-diff
```

## R01 reconciliation (next)

1. Load `source_records` from latest snapshot (metadata only, `--dry-run` first).
2. Match existing `source_files.url` → `source_records.original_url` / identity_key.
3. Link matches; quarantine mismatches for review.
4. Then fetch missing R02–R06 assets.

## Quote validator

Do not change `_validate_incident` without re-running:

```bash
python3 -m pipeline.tests.test_validation
```
