import { readFileSync } from "fs";
import path from "path";
import type { CanonicalContext } from "@/lib/rag/types";

export type SourceRecord = {
  externalId: string;
  identityKey: string;
  release: number;
  agency: string;
  type: string;
  title: string;
  description: string | null;
  originalUrl: string | null;
  sha256: string | null;
  byteSize: number | null;
  pageCount: number | null;
  classification: string | null;
  containsIncidents: boolean;
  acceptedFragmentCount: number;
  processingState: string;
  pairedSourceCount: number;
  catalogGeneratedAt: string | null;
  releaseDate: string | null;
  dvidsId: string | null;
};

export type FragmentRecord = {
  caseId: string;
  slug: string;
  title: string;
  summary: string;
  rawExcerpt: string;
  occurredAt: string | null;
  occurredAtText: string | null;
  locationText: string | null;
  country: string | null;
  region: string | null;
  branch: string | null;
  resolutionStatus: string | null;
  resolutionNotes: string | null;
  sourceExternalId: string | null;
  sourceFilename: string | null;
  release: string | null;
  documentClass: string | null;
  reportingUnit: string | null;
  sensorTypes: string[];
  shapeDescription: string | null;
  sizeDescription: string | null;
  occurredAtPrecision: string | null;
  altitudeFeet: number | null;
  durationSeconds: number | null;
};

type CoverageRow = {
  external_id: string;
  identity_key: string;
  release: number;
  agency: string;
  type: string;
  title: string;
  classification: string | null;
  extract_or_source_only: string | null;
  accepted_incident_count: number;
  qa_bucket: string;
  paired_source_count: number;
};

type OfficialRow = {
  external_id: string;
  title?: string;
  description?: string;
  original_url?: string;
  sha256?: string | null;
  byte_size?: number | null;
  release_date?: string;
  source_type?: string;
  agency?: string;
  metadata?: { dvids_video_id?: string | number };
};

type Graph = {
  canonical_events: {
    event_id: string;
    label: string;
    member_case_ids: string[];
    source_roles: { filename: string; role: string }[];
  }[];
  event_series: { series_id: string; label: string; event_ids: string[] }[];
};

type Catalog = {
  generatedAt: string | null;
  sources: SourceRecord[];
  fragments: FragmentRecord[];
  events: Graph["canonical_events"];
  series: Graph["event_series"];
  caseToEvent: Map<string, Graph["canonical_events"][number]>;
  eventToSeries: Map<string, Graph["event_series"][number]>;
  sourceOnlyIds: Set<string>;
};

let cached: Catalog | null = null;

function repoRoot(): string {
  const cwd = process.cwd();
  if (cwd.endsWith(`${path.sep}web`)) return path.resolve(cwd, "..");
  return cwd;
}

function readJson<T>(rel: string): T {
  return JSON.parse(readFileSync(path.join(repoRoot(), rel), "utf8")) as T;
}

function readJsonOptional<T>(rel: string, fallback: T): T {
  try {
    return readJson<T>(rel);
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code === "ENOENT") return fallback;
    throw error;
  }
}

const EXCLUDED_R3_SOURCES = new Set(["DOW-UAP-D088.pdf", "FBI-UAP-D013.pdf"]);

function externalIdFromFilename(filename: string | null): string | null {
  const match = (filename ?? "").match(/^([A-Z0-9]+-UAP-[A-Z0-9]+)/i);
  return match ? match[1].toUpperCase() : null;
}

function toFragment(row: Record<string, unknown>, release: string): FragmentRecord | null {
  const caseId = String(row.case_id ?? "");
  if (!caseId) return null;
  const sourceFilename = (row.source_filename as string | null) ?? null;
  const sourceExternalId =
    (row.source_external_id as string | null) ?? externalIdFromFilename(sourceFilename);
  return {
    caseId,
    slug: String(row.slug ?? caseId.toLowerCase()),
    title: String(row.title ?? caseId),
    summary: String(row.summary ?? ""),
    rawExcerpt: String(row.raw_excerpt ?? ""),
    occurredAt: (row.occurred_at as string | null) ?? null,
    occurredAtText: (row.occurred_at_text as string | null) ?? null,
    locationText: (row.location_text as string | null) ?? null,
    country: (row.country as string | null) ?? null,
    region: (row.region as string | null) ?? null,
    branch: (row.branch as string | null) ?? null,
    resolutionStatus: (row.resolution_status as string | null) ?? null,
    resolutionNotes: (row.resolution_notes as string | null) ?? null,
    sourceExternalId,
    sourceFilename,
    release: row.release != null ? String(row.release) : release,
    documentClass: (row.document_class as string | null) ?? null,
    reportingUnit: (row.reporting_unit as string | null) ?? null,
    sensorTypes: Array.isArray(row.sensor_types) ? row.sensor_types.map(String) : [],
    shapeDescription: (row.shape_description as string | null) ?? null,
    sizeDescription: (row.size_description as string | null) ?? null,
    occurredAtPrecision: (row.occurred_at_precision as string | null) ?? null,
    altitudeFeet: typeof row.altitude_feet === "number" ? row.altitude_feet : null,
    durationSeconds: typeof row.duration_seconds === "number" ? row.duration_seconds : null,
  };
}

function addFragments(
  byCase: Map<string, FragmentRecord>,
  rows: Record<string, unknown>[] | undefined,
  release: string,
  skip?: (row: Record<string, unknown>) => boolean,
) {
  for (const row of rows ?? []) {
    if (skip?.(row)) continue;
    const fragment = toFragment(row, release);
    if (!fragment || byCase.has(fragment.caseId)) continue;
    byCase.set(fragment.caseId, fragment);
  }
}

function loadFragments(): FragmentRecord[] {
  const byCase = new Map<string, FragmentRecord>();
  const smoke = readJsonOptional<{ validated_incidents?: Record<string, unknown>[] }>(
    "pipeline/reports/r2_smoke/extractions.json",
    {},
  );
  addFragments(byCase, smoke.validated_incidents, "02");

  const odni = readJsonOptional<{ validated?: Record<string, unknown>[]; filename?: string }>(
    "pipeline/reports/r2_complete/odni_extraction.json",
    {},
  );
  addFragments(
    byCase,
    (odni.validated ?? []).map((row) => ({
      ...row,
      source_filename: row.source_filename ?? odni.filename ?? "ODNI-UAP-D001.pdf",
    })),
    "02",
  );

  const r3 = readJsonOptional<{ validated_incidents?: Record<string, unknown>[] }>(
    "pipeline/reports/r3_full/extractions.json",
    {},
  );
  addFragments(byCase, r3.validated_incidents, "03", (row) =>
    EXCLUDED_R3_SOURCES.has(String(row.source_filename ?? "")),
  );

  const truncation = readJsonOptional<{ results?: { validated_incidents?: Record<string, unknown>[] }[] }>(
    "pipeline/reports/r3_truncation_fix/results.json",
    {},
  );
  for (const result of truncation.results ?? []) {
    addFragments(byCase, result.validated_incidents, "03");
  }

  for (const [file, release] of [
    ["pipeline/reports/r4_local/extractions.json", "04"],
    ["pipeline/reports/r5_local/extractions.json", "05"],
    ["pipeline/reports/r6_local/extractions.json", "06"],
  ] as const) {
    const payload = readJsonOptional<{ validated_incidents?: Record<string, unknown>[] }>(file, {});
    addFragments(byCase, payload.validated_incidents, release);
  }
  return [...byCase.values()];
}

function loadChecksums(): Map<string, { sha256: string | null; byteSize: number | null }> {
  const files = [
    "pipeline/reports/r3_full/cache_manifest.json",
    "pipeline/reports/r4_local/cache_manifest.json",
    "pipeline/reports/r5_local/cache_manifest.json",
    "pipeline/reports/r6_local/cache_manifest.json",
  ];
  const map = new Map<string, { sha256: string | null; byteSize: number | null }>();
  for (const file of files) {
    try {
      const payload = readJson<{ results?: { external_id?: string; sha256?: string; byte_size?: number }[] }>(file);
      for (const row of payload.results ?? []) {
        if (!row.external_id) continue;
        map.set(row.external_id, {
          sha256: row.sha256 ?? null,
          byteSize: row.byte_size ?? null,
        });
      }
    } catch {
      // A missing local cache manifest leaves checksums blank.
    }
  }
  return map;
}

function loadCatalog(): Catalog {
  if (cached) return cached;
  const coverage = readJsonOptional<{ generated_at?: string; records: CoverageRow[] }>(
    "pipeline/reports/corpus_qa/source_coverage.json",
    { records: [] },
  );
  const official = readJsonOptional<OfficialRow[]>(
    "pipeline/snapshots/pursue/2026-09-18-official/records.json",
    [],
  );
  const graph = readJsonOptional<Graph>("pipeline/reports/corpus_qa/linker/full_graph.json", {
    canonical_events: [],
    event_series: [],
  });
  const officialById = new Map(official.map((row) => [row.external_id, row]));
  const checksums = loadChecksums();
  const fragments = loadFragments();

  const sources: SourceRecord[] = coverage.records.map((row) => {
    const meta = officialById.get(row.external_id);
    const sum = checksums.get(row.external_id);
    return {
      externalId: row.external_id,
      identityKey: row.identity_key,
      release: row.release,
      agency: row.agency,
      type: row.type,
      title: row.title || meta?.title || row.external_id,
      description: meta?.description ?? null,
      originalUrl: meta?.original_url ?? null,
      sha256: sum?.sha256 ?? meta?.sha256 ?? null,
      byteSize: sum?.byteSize ?? meta?.byte_size ?? null,
      pageCount: null,
      classification: row.classification,
      containsIncidents: (row.accepted_incident_count ?? 0) > 0,
      acceptedFragmentCount: row.accepted_incident_count ?? 0,
      processingState: row.qa_bucket,
      pairedSourceCount: row.paired_source_count ?? 0,
      catalogGeneratedAt: coverage.generated_at ?? null,
      releaseDate: meta?.release_date ?? null,
      dvidsId: meta?.metadata?.dvids_video_id != null ? String(meta.metadata.dvids_video_id) : null,
    };
  });

  const caseToEvent = new Map<string, Graph["canonical_events"][number]>();
  for (const event of graph.canonical_events) {
    for (const caseId of event.member_case_ids ?? []) {
      caseToEvent.set(caseId.toUpperCase(), event);
    }
  }
  const eventToSeries = new Map<string, Graph["event_series"][number]>();
  for (const series of graph.event_series) {
    for (const eventId of series.event_ids ?? []) eventToSeries.set(eventId, series);
  }

  const sourceOnlyIds = new Set(
    sources
      .filter((source) => source.externalId && !source.containsIncidents)
      .map((source) => source.externalId.toUpperCase()),
  );

  cached = {
    generatedAt: coverage.generated_at ?? null,
    sources,
    fragments,
    events: graph.canonical_events,
    series: graph.event_series,
    caseToEvent,
    eventToSeries,
    sourceOnlyIds,
  };
  return cached;
}

export function getCorpusStats() {
  const catalog = loadCatalog();
  const releases = new Set(catalog.sources.map((source) => source.release));
  const fragmentIds = new Set<string>();
  for (const event of catalog.events) {
    for (const caseId of event.member_case_ids ?? []) fragmentIds.add(caseId.toUpperCase());
  }
  return {
    officialRecords: catalog.sources.length,
    fragments: fragmentIds.size,
    canonicalEvents: catalog.events.length,
    releases: releases.size,
    eventSeries: catalog.series.length,
    seriesEventCounts: catalog.series.map((series) => ({
      seriesId: series.series_id,
      label: series.label,
      events: series.event_ids.length,
    })),
    audioRecords: catalog.sources.filter((source) => source.type === "audio").length,
    catalogGeneratedAt: catalog.generatedAt,
  };
}

export function listReleases() {
  const catalog = loadCatalog();
  const grouped = new Map<number, SourceRecord[]>();
  for (const source of catalog.sources) {
    const rows = grouped.get(source.release) ?? [];
    rows.push(source);
    grouped.set(source.release, rows);
  }
  return [...grouped.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([release, rows]) => ({
      release,
      label: `Release ${String(release).padStart(2, "0")}`,
      records: rows.length,
      pdfs: rows.filter((row) => row.type === "pdf").length,
      media: rows.filter((row) => row.type !== "pdf").length,
      agencies: [...new Set(rows.map((row) => row.agency))].sort(),
      states: [...new Set(rows.map((row) => row.processingState))].sort(),
      acceptedFragments: rows.reduce((sum, row) => sum + row.acceptedFragmentCount, 0),
    }));
}

export function getRelease(releaseNumber: number) {
  return listReleases().find((release) => release.release === releaseNumber) ?? null;
}

export function listSources(filters?: {
  release?: number;
  agency?: string;
  type?: string;
  documentClass?: string;
  state?: string;
}) {
  return loadCatalog().sources.filter((source) => {
    if (filters?.release && source.release !== filters.release) return false;
    if (filters?.agency && source.agency !== filters.agency) return false;
    if (filters?.type && source.type !== filters.type) return false;
    if (filters?.documentClass && source.classification !== filters.documentClass) return false;
    if (filters?.state && source.processingState !== filters.state) return false;
    return true;
  });
}

export function sourceFacets() {
  const sources = loadCatalog().sources;
  const uniq = (values: (string | null)[]) =>
    [...new Set(values.filter((value): value is string => Boolean(value)))].sort();
  return {
    agencies: uniq(sources.map((source) => source.agency)),
    types: uniq(sources.map((source) => source.type)),
    classes: uniq(sources.map((source) => source.classification)),
    states: uniq(sources.map((source) => source.processingState)),
    releases: [...new Set(sources.map((source) => source.release))].sort((a, b) => a - b),
  };
}

export function getSource(externalId: string): SourceRecord | null {
  const decoded = decodeURIComponent(externalId);
  return loadCatalog().sources.find((source) => source.externalId === decoded) ?? null;
}

export function fragmentsForSource(externalId: string): FragmentRecord[] {
  return loadCatalog().fragments.filter((fragment) => fragment.sourceExternalId === externalId);
}

export function eventsForSource(externalId: string) {
  const catalog = loadCatalog();
  const needle = externalId.toLowerCase();
  return catalog.events
    .filter((event) =>
      (event.source_roles ?? []).some((role) => role.filename.toLowerCase().includes(needle)),
    )
    .map((event) => ({
      eventId: event.event_id,
      label: event.label,
      memberCaseIds: event.member_case_ids,
      roles: event.source_roles.filter((role) => role.filename.toLowerCase().includes(needle)),
      series: catalog.eventToSeries.get(event.event_id) ?? null,
    }));
}

export function getFragmentBySlug(slug: string): FragmentRecord | null {
  const catalog = loadCatalog();
  return (
    catalog.fragments.find((fragment) => fragment.slug === slug || fragment.caseId.toLowerCase() === slug.toLowerCase()) ??
    null
  );
}

export function listAudio(): SourceRecord[] {
  return loadCatalog().sources.filter((source) => source.type === "audio");
}

export function identityForCase(caseId: string): CanonicalContext | null {
  const catalog = loadCatalog();
  const event = catalog.caseToEvent.get(caseId.toUpperCase());
  if (!event) return null;
  const series = catalog.eventToSeries.get(event.event_id);
  return {
    eventId: event.event_id,
    eventLabel: event.label,
    memberCaseIds: event.member_case_ids,
    sourceRoles: event.source_roles ?? [],
    seriesId: series?.series_id,
    seriesLabel: series?.label,
    seriesEventCount: series?.event_ids.length,
  };
}

export function sourceOnlyIds(): string[] {
  return [...loadCatalog().sourceOnlyIds];
}

export function listFragments(): FragmentRecord[] {
  return loadCatalog().fragments;
}

export function allCaseIds(): string[] {
  return loadCatalog().fragments.map((fragment) => fragment.caseId).filter(Boolean);
}

export function searchSources(question: string, limit = 6): SourceRecord[] {
  const tokens = tokenize(question);
  const programs = matchedPrograms(question);
  if (tokens.length === 0 && programs.length === 0) return [];

  const scored = loadCatalog().sources.map((source) => {
    const hay = [source.title, source.description ?? "", source.agency, source.externalId, source.type]
      .join(" ")
      .toLowerCase();
    let score = 0;
    for (const token of tokens) {
      if (!hay.includes(token)) continue;
      score += token.length >= 4 ? 3 : 1;
    }
    for (const program of programs) {
      if (hay.includes(program.phrase)) score += 20;
      else if (source.title.toLowerCase().includes(program.short)) score += 12;
    }
    return { source, score };
  });
  return scored
    .filter((row) => row.score >= 3)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((row) => row.source);
}

/** Known Air Force investigation programs that live mainly in released files, not case titles. */
export function matchedPrograms(question: string): { phrase: string; short: string; label: string }[] {
  const hits: { phrase: string; short: string; label: string }[] = [];
  const text = question.toLowerCase();
  if (/\bproject\s+sign\b/.test(text) || (/\bsign\b/.test(text) && /\b(blue\s*book|grudge|before|after|project)\b/.test(text))) {
    hits.push({ phrase: "project sign", short: "sign", label: "Project Sign" });
  }
  if (/\bproject\s+grudge\b/.test(text) || /\bgrudge\b/.test(text)) {
    hits.push({ phrase: "project grudge", short: "grudge", label: "Project Grudge" });
  }
  if (/\bproject\s+blue\s*book\b/.test(text) || /\bblue\s*books?\b/.test(text) || /\bbluebook\b/.test(text)) {
    hits.push({ phrase: "project blue book", short: "blue book", label: "Project Blue Book" });
  }
  return hits;
}

export function searchProgramSources(question: string, limit = 8): SourceRecord[] {
  const programs = matchedPrograms(question);
  if (programs.length === 0) return [];
  const scored = loadCatalog().sources.map((source) => {
    const hay = [source.title, source.description ?? "", source.externalId].join(" ").toLowerCase();
    let score = 0;
    for (const program of programs) {
      if (hay.includes(program.phrase)) score += 20;
      else if (source.title.toLowerCase().includes(program.short)) score += 8;
    }
    return { source, score };
  });
  return scored
    .filter((row) => row.score > 0 && row.source.externalId)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((row) => row.source);
}

export function searchLocalFragments(question: string, limit = 8): FragmentRecord[] {
  return scoreLocalFragments(question)
    .slice(0, limit)
    .map((row) => row.fragment);
}

/** Place, year, agency, and case id outweigh a passing mention inside a quote. */
export function scoreLocalFragments(question: string): { fragment: FragmentRecord; score: number }[] {
  const tokens = tokenize(question);
  if (tokens.length === 0) return [];
  const catalog = loadCatalog();
  const fields = (fragment: FragmentRecord, eventLabel: string): [string, number][] => [
    [fragment.locationText ?? "", 6],
    [fragment.occurredAt ?? "", 6],
    [fragment.caseId, 4],
    [fragment.branch ?? "", 4],
    [fragment.title, 4],
    [eventLabel, 3],
    [fragment.summary, 2],
    [fragment.rawExcerpt, 1],
  ];
  return catalog.fragments
    .map((fragment) => {
      const eventLabel = catalog.caseToEvent.get(fragment.caseId.toUpperCase())?.label ?? "";
      let score = 0;
      for (const [text, weight] of fields(fragment, eventLabel)) {
        const hay = text.toLowerCase();
        for (const token of tokens) {
          if (hay.includes(token)) score += weight * (token.length > 4 ? 2 : 1);
        }
      }
      return { fragment, score };
    })
    .filter((row) => row.score >= 4)
    .sort((a, b) => b.score - a.score);
}

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((token) => token.length > 2 && !STOP.has(token));
}

const STOP = new Set([
  "the", "and", "for", "with", "that", "this", "from", "what", "which", "about", "does", "did",
  "are", "was", "were", "have", "has", "into", "over", "under", "archive", "records", "record",
  "government", "contain", "contains", "any", "there", "they", "related", "sighting", "sightings",
  "incident", "incidents", "file", "files", "some", "when", "where", "who", "how", "why", "not",
  "but", "all", "can", "you", "near", "around", "happened", "happen", "investigate", "investigated",
  "investigation", "during", "after", "before",
]);
