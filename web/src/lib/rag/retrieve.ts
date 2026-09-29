import { identityForCase, listFragments, listSources, matchedPrograms, scoreLocalFragments, searchProgramSources, searchSources, sourceOnlyIds, type SourceRecord } from "@/lib/corpus/catalog";
import { formatFacts, formatFileLines } from "./context";
import { getRagConfig } from "./config";
import { embedQuestion } from "./embed";
import { getSupabaseServer } from "@/lib/supabase";
import type { RetrievedFile, RetrievedIncident } from "./types";

const MATCH_THRESHOLD = 0.45;
const MATCH_COUNT = 12;
const STRUCTURED_LIMIT = 8;

const AGENCIES: { pattern: RegExp; code: string; name: string }[] = [
  { pattern: /\bfbi\b/i, code: "FBI", name: "FBI" },
  { pattern: /\busaf\b|\bair force\b/i, code: "USAF", name: "Air Force" },
  { pattern: /\bnavy\b|\busn\b/i, code: "USN", name: "Navy" },
  { pattern: /\bnasa\b/i, code: "NASA", name: "NASA" },
  { pattern: /\bcia\b/i, code: "CIA", name: "CIA" },
  { pattern: /\barmy\b/i, code: "USA", name: "Army" },
];

const TOPIC_SKIP = new Set([
  "detection", "involved", "objects", "object", "flying", "report", "reports",
  "light", "lights", "seen", "multiple", "related", "sighting", "sightings",
  "tell", "about", "please", "give", "show", "describe", "explain", "known",
  "named", "called", "mention", "mentions", "happen", "happened", "there",
  "these", "those", "with", "from", "into", "over", "near", "file", "files",
  "many", "some", "most", "audio", "video", "image", "images", "photo", "photos",
  "document", "documents", "recording", "recordings", "archive", "records",
  "released", "case", "cases", "incident", "incidents", "investigate",
  "investigated", "investigation", "actually", "really", "seriously", "weird",
  "stuff", "something", "anything", "whatever", "kinda", "just", "like", "okay",
  "well", "maybe", "still", "ever", "anyone", "someone", "everyone", "compare",
  "coverage", "early", "before", "after", "oldest", "newest", "earliest", "latest",
  "here", "they", "them", "your", "mine", "ours", "real", "true", "come", "came",
  "came", "does", "dont", "isn't", "aint", "kids", "asked", "heard", "think",
  "know", "want", "need", "help", "look", "looking", "find", "found", "says",
  "said", "saying", "files", "file",
]);

const TOPIC_STOP = new Set([
  "what", "when", "where", "which", "about", "there", "these", "those", "from",
  "with", "that", "this", "have", "been", "were", "does", "into", "over", "near",
  "tell", "please", "give", "show", "describe", "explain", "was", "were", "are",
  "did", "can", "you", "how", "why", "who", "the", "and", "for", "not", "but",
]);

let mappedCache: Set<string> | null = null;

export async function retrieveEvidence(question: string): Promise<{
  incidents: RetrievedIncident[];
  files: RetrievedFile[];
  facts: string;
  scopedFiles: string;
  scope: RetrievedFile[];
  allowedCaseIds: string[];
  latencyMs: number;
  sourceOnlyIds: string[];
  note: string;
}> {
  const started = Date.now();
  const config = getRagConfig();
  const structured = await retrieveStructured(question);
  const lexical = structured.incidents.length > 0 ? [] : retrieveLocal(question);
  const vector =
    structured.incidents.length > 0 || config.evidenceSource === "local" ? [] : await retrieveVector(question);
  const files = retrieveFiles(question);
  const programs = matchedPrograms(question);
  const mapped = await mappedCaseIds();
  const incidents = structured.incidents.length > 0 ? structured.incidents : mergeIncidents(lexical, vector);
  const scope = scopeFiles(question);
  let sourceOnly: string[] = [];
  let facts = "";
  let scopedFiles = "";
  let note = structured.note;
  try {
    sourceOnly = sourceOnlyIds();
    facts = formatFacts(listFragments(), listSources(), mapped.size);
    scopedFiles = formatFileLines(scope);
    if (programs.length > 0 && files.length > 0) {
      const labels = programs.map((program) => program.label).join(" and ");
      const programNote = `Released files about ${labels} are listed under Files found for this question.`;
      note = note ? `${note}\n${programNote}` : programNote;
    }
  } catch (error) {
    console.warn("[ask] source catalog unavailable:", (error as Error).message);
  }
  return {
    incidents,
    files,
    facts,
    scopedFiles,
    scope: scope.map(toRetrievedFile),
    allowedCaseIds: incidents.map((incident) => incident.case_id).filter(Boolean),
    latencyMs: Date.now() - started,
    sourceOnlyIds: sourceOnly,
    note,
  };
}

function questionYear(question: string): string | null {
  return question.match(/\b((?:19|20)\d{2})\b/)?.[1] ?? null;
}

function questionDecade(question: string): { start: string; end: string; label: string } | null {
  const match =
    question.match(/\b((?:19|20)\d)0s\b/i) ||
    question.match(/\b((?:19|20)\d{2})s\b/i) ||
    question.match(/\b(\d{2})s\b/i);
  if (!match) return null;
  let decade = match[1].toLowerCase();
  if (decade.length === 2) {
    const n = Number(decade);
    decade = n >= 90 ? `19${decade}` : n <= 20 ? `20${decade}` : `19${decade}`;
  }
  if (decade.length === 3) decade = `${decade}0`;
  if (!/^(?:19|20)\d{2}$/.test(decade)) return null;
  const startYear = Number(decade.slice(0, 3) + "0");
  return {
    start: `${startYear}-01-01`,
    end: `${startYear + 9}-12-31`,
    label: `${startYear}s`,
  };
}

function questionAgency(question: string): { code: string; name: string } | null {
  return AGENCIES.find((agency) => agency.pattern.test(question)) ?? null;
}

function washingtonDc(question: string): boolean {
  return (
    /washington\s+d\.?\s*c\.?/i.test(question) ||
    /district of columbia/i.test(question) ||
    /\bwhite house\b/i.test(question) ||
    /\b(u\.?s\.?\s+)?capitol\b/i.test(question)
  );
}

function extremeOrder(question: string): "asc" | "desc" | null {
  if (/\b(oldest|earliest|first)\b/i.test(question)) return "asc";
  if (/\b(newest|latest|most recent)\b/i.test(question)) return "desc";
  return null;
}

function unresolvedAsk(question: string): boolean {
  return /\b(unexplained|unresolved|unidentified|unknown)\b/i.test(question) &&
    /\b(how many|count|number|are there)\b/i.test(question);
}

function topicQuery(question: string): string | null {
  if (/\b(how many|list|all|every)\b/i.test(question) && !/\b(unexplained|unresolved)\b/i.test(question)) {
    return null;
  }

  const names = [...question.matchAll(/\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b/g)]
    .map((match) => match[1])
    .filter((name) => !/^(United States|Air Force|New York|Los Angeles|White House)$/i.test(name));
  if (names.length > 0) {
    return names.sort((a, b) => b.length - a.length)[0];
  }

  const tokens = question
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(
      (token) =>
        token.length >= 4 &&
        !TOPIC_SKIP.has(token) &&
        !TOPIC_STOP.has(token) &&
        !/^(?:19|20)\d{2}$/.test(token) &&
        !/^\d+s$/.test(token),
    );
  if (tokens.length === 0) return null;
  return tokens.sort((a, b) => b.length - a.length || a.localeCompare(b))[0];
}

async function retrieveStructured(question: string): Promise<{ incidents: RetrievedIncident[]; note: string }> {
  const year = questionYear(question);
  const decade = questionDecade(question);
  const agency = questionAgency(question);
  const place = washingtonDc(question);
  const extreme = extremeOrder(question);
  const unresolved = unresolvedAsk(question);
  const topic = !year && !decade && !agency && !place && !extreme && !unresolved ? topicQuery(question) : null;
  if (!year && !decade && !agency && !place && !extreme && !unresolved && !topic) {
    return { incidents: [], note: "" };
  }

  try {
    const sb = getSupabaseServer();
    let query = sb
      .from("incidents")
      .select("id, slug, case_id, title, summary, raw_excerpt, occurred_at, location_text, branch, resolution_status", {
        count: "exact",
      })
      .eq("flagged", false);

    let note = "";
    let orderColumn = "case_id";
    let ascending = true;

    if (extreme) {
      query = query.not("occurred_at", "is", null);
      orderColumn = "occurred_at";
      ascending = extreme === "asc";
      note = extreme === "asc" ? "oldest dated records" : "newest dated records";
    } else if (unresolved) {
      query = query.eq("resolution_status", "unresolved");
      note = "unresolved cases";
    } else if (year && agency) {
      query = query.ilike("case_id", `${year}-${agency.code}%`);
      note = `${agency.name} records from ${year}`;
    } else if (decade) {
      query = query.gte("occurred_at", decade.start).lte("occurred_at", decade.end);
      orderColumn = "occurred_at";
      note = `records from the ${decade.label}`;
    } else if (year) {
      query = query.ilike("case_id", `${year}-%`);
      note = `records from ${year}`;
    } else if (place) {
      query = query.or(
        [
          'location_text.ilike."%Washington, D.C.%"',
          'location_text.ilike."%Washington D.C.%"',
          'title.ilike."%Washington, D.C.%"',
          'title.ilike."%Washington D.C.%"',
          'location_text.ilike."%District of Columbia%"',
          'title.ilike."%District of Columbia%"',
          'title.ilike."%White House%"',
          'summary.ilike."%White House%"',
          'title.ilike."%Capitol%"',
          'summary.ilike."%Capitol%"',
        ].join(","),
      );
      note = "records about Washington, D.C.";
    } else if (agency) {
      query = query.ilike("case_id", `%-${agency.code}-%`);
      note = `${agency.name} records`;
    } else if (topic) {
      const needle = topic.replace(/"/g, "");
      query = query.or(
        `title.ilike."%${needle}%",summary.ilike."%${needle}%",location_text.ilike."%${needle}%",case_id.ilike."%${needle}%"`,
      );
      note = `records that mention ${topic}`;
    }

    const { data, error, count } = await query.order(orderColumn, { ascending }).limit(STRUCTURED_LIMIT);
    if (error) throw new Error(error.message);
    const incidents = (data ?? []).map(toStructuredIncident);
    const total = count ?? incidents.length;
    const shown = incidents.length;
    let fullNote = "";
    if (unresolved && shown > 0) {
      fullNote = `There are ${total} unresolved cases in the archive. ${shown} are shown below.`;
    } else if (extreme && shown > 0) {
      fullNote = `These are among the ${note} in the archive.`;
    } else if (shown > 0 && total > shown) {
      fullNote = `There are ${total} ${note}. ${shown} are shown below.`;
    }
    return { incidents, note: fullNote };
  } catch (error) {
    console.warn("[ask] field search unavailable:", (error as Error).message);
    return { incidents: [], note: "" };
  }
}

function toStructuredIncident(row: Record<string, string | null>): RetrievedIncident {
  const caseId = String(row.case_id ?? "");
  return {
    id: String(row.id ?? caseId),
    slug: row.slug,
    case_id: caseId,
    title: String(row.title ?? ""),
    summary: String(row.summary ?? ""),
    raw_excerpt: String(row.raw_excerpt ?? ""),
    occurred_at: row.occurred_at,
    location_text: row.location_text,
    branch: row.branch,
    resolution_status: row.resolution_status,
    identity: caseId ? identityForCase(caseId) : null,
    lexicalScore: 100,
  };
}

function retrieveLocal(question: string): RetrievedIncident[] {
  return scoreLocalFragments(question)
    .slice(0, MATCH_COUNT)
    .map(({ fragment, score }) => ({
      id: fragment.caseId,
      slug: fragment.slug,
      case_id: fragment.caseId,
      title: fragment.title,
      summary: fragment.summary,
      raw_excerpt: fragment.rawExcerpt,
      occurred_at: fragment.occurredAt,
      location_text: fragment.locationText,
      branch: fragment.branch,
      resolution_status: fragment.resolutionStatus,
      identity: identityForCase(fragment.caseId),
      lexicalScore: score,
    }));
}

function retrieveFiles(question: string): RetrievedFile[] {
  try {
    const programHits = searchProgramSources(question, 8).map(toRetrievedFile);
    const lexicalHits = searchSources(question, 8)
      .filter((source) => Boolean(source.externalId))
      .map(toRetrievedFile);
    const merged = new Map<string, RetrievedFile>();
    for (const file of [...programHits, ...lexicalHits]) {
      if (!file.id || merged.has(file.id)) continue;
      merged.set(file.id, file);
    }
    return [...merged.values()].slice(0, 8);
  } catch (error) {
    console.warn("[ask] file search unavailable:", (error as Error).message);
    return [];
  }
}

function scopeFiles(question: string): SourceRecord[] {
  const text = question.toLowerCase();
  if (!/\b(how many|list|all|every)\b/.test(text)) return [];
  let type = "";
  if (/\baudio\b|\brecordings?\b/.test(text)) type = "audio";
  else if (/\bvideos?\b/.test(text)) type = "video";
  else if (/\b(images?|photos?|pictures?)\b/.test(text)) type = "image";
  else if (/\b(documents?|pdfs?)\b/.test(text)) type = "pdf";
  if (!type) return [];
  try {
    return listSources().filter((source) => source.externalId && source.type === type);
  } catch (error) {
    console.warn("[ask] file list unavailable:", (error as Error).message);
    return [];
  }
}

function toRetrievedFile(source: SourceRecord): RetrievedFile {
  return {
    id: source.externalId,
    title: source.title,
    agency: source.agency,
    kind: source.type,
    note: source.description ? source.description.slice(0, 1400) : null,
    href: `/source/${source.externalId}`,
  };
}

async function retrieveVector(question: string): Promise<RetrievedIncident[]> {
  const sb = getSupabaseServer();
  const queryVec = await embedQuestion(question);
  const { data: matches, error } = await sb.rpc("match_incidents", {
    query_embedding: queryVec,
    match_threshold: MATCH_THRESHOLD,
    match_count: MATCH_COUNT,
  });
  if (error) throw new Error(error.message);
  const rows = matches ?? [];
  if (rows.length === 0) return [];

  const ids = rows.map((row: { id: string }) => row.id);
  const { data: slugRows } = await sb.from("incidents").select("id, slug").in("id", ids);
  const slugMap = new Map((slugRows ?? []).map((row: { id: string; slug: string | null }) => [row.id, row.slug]));

  return rows.map((row: Record<string, string | number | null>) => ({
    id: String(row.id),
    slug: slugMap.get(String(row.id)) ?? null,
    case_id: String(row.case_id ?? ""),
    title: String(row.title ?? ""),
    summary: String(row.summary ?? ""),
    raw_excerpt: String(row.raw_excerpt ?? ""),
    occurred_at: row.occurred_at != null ? String(row.occurred_at) : null,
    location_text: row.location_text != null ? String(row.location_text) : null,
    branch: row.branch != null ? String(row.branch) : null,
    resolution_status: row.resolution_status != null ? String(row.resolution_status) : null,
    similarity: typeof row.similarity === "number" ? row.similarity : Number(row.similarity ?? 0),
    identity: safeIdentity(row.case_id ? String(row.case_id) : null),
  }));
}

function mergeIncidents(lexical: RetrievedIncident[], vector: RetrievedIncident[]): RetrievedIncident[] {
  const ranked = new Map<string, { incident: RetrievedIncident; rank: number }>();
  const consider = (incident: RetrievedIncident, rank: number) => {
    const key = incident.case_id.toUpperCase();
    if (!key) return;
    const prev = ranked.get(key);
    if (!prev || rank > prev.rank) ranked.set(key, { incident, rank });
  };
  for (const incident of lexical) consider(incident, incident.lexicalScore ?? 0);
  for (const incident of vector) consider(incident, (incident.similarity ?? 0) * 20);
  return [...ranked.values()]
    .sort((a, b) => b.rank - a.rank)
    .slice(0, 8)
    .map((row) => row.incident);
}

async function mappedCaseIds(): Promise<Set<string>> {
  if (mappedCache) return mappedCache;
  try {
    const sb = getSupabaseServer();
    const { data, error } = await sb
      .from("incidents")
      .select("case_id")
      .not("lat", "is", null)
      .eq("flagged", false)
      .limit(1000);
    if (error) throw new Error(error.message);
    const ids = new Set<string>();
    for (const row of data ?? []) {
      if (row.case_id) ids.add(String(row.case_id).toUpperCase());
    }
    mappedCache = ids;
    return ids;
  } catch (error) {
    console.warn("[ask] map points unavailable:", (error as Error).message);
    return new Set();
  }
}

function safeIdentity(caseId: string | null) {
  if (!caseId) return null;
  try {
    return identityForCase(caseId);
  } catch (error) {
    console.warn("[ask] canonical context unavailable:", (error as Error).message);
    return null;
  }
}
