import cache from "./example-cache.json";

export type CachedCitation = {
  id: string;
  slug: string | null;
  case_id: string;
  title: string;
  occurred_at: string | null;
  location_text: string | null;
  href?: string;
};

export type CachedExample = {
  answer: string;
  citations: CachedCitation[];
  citation_status: string;
};

function normalizeQuestion(question: string): string {
  return question.trim().replace(/\s+/g, " ").toLowerCase();
}

const byNormalized = new Map<string, CachedExample>();
for (const [question, entry] of Object.entries(cache as Record<string, CachedExample>)) {
  byNormalized.set(normalizeQuestion(question), entry);
}

/** Exact match (normalized whitespace/case) against the four canned Ask examples. */
export function getCachedExample(question: string): CachedExample | null {
  return byNormalized.get(normalizeQuestion(question)) ?? null;
}
