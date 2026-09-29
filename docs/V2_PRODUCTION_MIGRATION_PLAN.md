# V2 production migration plan

**Date:** 2026-09-28  
**Status:** Design only. The local gate is `LOCAL_RELEASE_READY`. Do not run these steps until a later instruction says to start.  
**Corpus gate:** `CORPUS_QA_COMPLETE` (`docs/V2_R1_R6_CORPUS_QA.md`).  
**Delta:** `docs/V2_PRODUCTION_DELTA.md`.

GPT-6 stays behind `RAG_PROVIDER`. This plan loads data first. Enabling GPT-6 is a later flag flip, not a step in the data load. If Ask misbehaves after deploy, set `RAG_PROVIDER=anthropic` and leave the new rows in place.

## Order

### 1. Backup

Snapshot the database before any DDL or DML. Record incident count (480), unflagged count (380), flagged count (100), `source_files` (181), `source_records` (450), and `incident_sources` (476). Stop if those counts have moved.

### 2. Apply remaining schema

Already applied: `004` source registry, `005` media assets, `006` public stats exclude flagged, `007` `incident_sources`.

Still design-only:

- `db/migrations/008_ingestion_state_DESIGN_ONLY.sql`
- `db/migrations/009_canonical_events_DESIGN_ONLY.sql`

Review both against the live schema, then apply. Do not apply them in this planning pass.

### 3. Populate `source_records`

No bulk insert. The 450 official rows are already there. Update nulls only: document class, `contains_incidents`, checksum, byte size, and ingestion state for rows whose local PDF now exists. Match on `(provider, identity_key)`.

FBI-UAP-D014 stays two keys: `pursue:FBI-UAP-D014` (R4 PDF) and `pursue:FBI-UAP-D014:image` (R3 rendering).

### 4. Reconcile existing R1 `source_files`

160 files are already linked. Do not re-download them.

Manual links only, after a human checks the URL pair:

- Southern United States 2020 file stays its own document. It is not official `DOW-UAP-D020` (Iraq 2023).
- Gemini 7 transcript (`NASA-UAP-D3`) links to the official NASA R1 record if the bytes match.
- `65_HS1-..._Serial_153` links to the official serial-153 record if the bytes match.
- `59_64634_711.5612[7-2852` stays unlinked until the official PDF is fetched and checksummed.

The four unflagged incidents on those files stay as they are. Linking the file is the change. Re-extraction is not.

Leave the 17 slideshow JPGs unlinked to official records.

### 5. Insert new R2–R6 `source_files`

Insert the 154 locally cached PDFs (R2 6, R3 53, R4 14, R5 22, R6 59). Skip a row when `url` already exists (R2 smoke uploads). Store sha256, byte size, page count, and `source_record_id`.

Do not upload the 180 media binaries in this step. Their `source_records` rows already describe them.

### 6. Insert validated incident fragments

Insert the 203 R2–R6 accepted fragments. Each row needs `source_file_id`, `raw_excerpt`, case id, and the local extraction metadata. Refuse the insert if the excerpt is empty.

Do not insert flagged duplicates. Do not insert quote-rejected or evidence-insufficient candidates.

### 7. Preserve flagged existing rows

The 100 `duplicate_excerpt` rows stay flagged. Public stats continue to exclude them (`006`). Do not delete them in this release.

### 8. Insert `incident_sources`

One primary `incident_sources` row per new fragment, pointing at the official `source_record` and the new `source_file`. Add rows for the four R1 incidents above once their files are linked.

### 9. Insert canonical events

575 events from `pipeline/reports/corpus_qa/linker/`. Incidents are not rewritten. `auto_merged` stays false.

### 10. Insert event members

583 memberships: every linker fragment belongs to exactly one event. 572 events have one member. Three events have more than one member because of intra-source continuity, not because two files were collapsed.

### 11. Insert source relationships

Insert the 3 auto-supported `event_source` rows (`media_for_event`, `analysis_of_event`). Store the 24 `review_supported` place overlaps as review records, not as merges. Do not insert cross-release `same_event` rows: the corpus QA run produced 0.

Western US is one series row with 21 event ids. FBI-UAP-D014’s correspondence PDF is not a member of that series.

### 12. Embed new accepted incidents

Embed the 203 new fragments with Voyage `voyage-3` (1024-d, zero-pad to 1536). Do not re-embed the existing 380. Do not change `vector(1536)`. Embedding migration is V2.1.

### 13. Rebuild stats and views

Refresh `v_stats` and any release/source views after the inserts. Expected public fragment count: 380 + 203 = 583, with flagged rows still excluded. Publish canonical-event counts from the new tables, not by renaming the fragment count.

### 14. QA production with shadow queries

Before any new UI route is linked in nav:

- incident count unflagged = 583
- flagged still 100
- `source_records` still 450, no duplicate identity keys
- every new incident has a non-empty excerpt and an `incident_sources` row
- every event member’s case id exists
- Western US series has 21 events and does not include FBI-UAP-D014.pdf
- Colorado Springs still has one event, with media and analysis attached, and no extra incident rows
- Ask retrieval against the new embeddings returns R2–R6 case ids on a fixture question (Sary Shagan, Tremonton, green fireballs)

### 15. Only then expose new UI

Ship `/releases`, `/sources`, and `/audio` after the shadow queries pass. Homepage copy uses fragments and canonical events as separate numbers. Ask can stay on Anthropic until the RAG eval gate passes. Turning on GPT-6 is `RAG_PROVIDER=openai` and does not require another data migration.

## Abort

Stop the load and restore the backup if any of these happen:

- an unflagged R1 excerpt changes
- a flagged row becomes public
- incident insert count is not 203
- a new accepted row has an empty excerpt
- FBI-UAP-D014 PDF is attached to the Western US series
- `source_records` count leaves 450 without an explained split of a duplicate id

## Explicitly out of this plan

- Re-extracting R1
- Linker V1.1
- Replacing Voyage embeddings
- Switching extraction off Claude Haiku 4.5
- Enabling GPT-6 as part of the data transaction
