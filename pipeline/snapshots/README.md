# Manifest snapshots

Immutable captures of official government manifests.

```text
pursue/YYYY-MM-DD/
  uap-data.csv      # ignored by git (large)
  records.json      # ignored by git (large)
  manifest.json     # tracked — counts, sha256, provenance
  manifest.sha256   # tracked
  diff.json         # optional, from pipeline.diff_manifest
```

Generate with:

```bash
python -m pipeline.discover --provider pursue --snapshot-date YYYY-MM-DD
```
