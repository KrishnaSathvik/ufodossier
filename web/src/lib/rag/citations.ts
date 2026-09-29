import type { CitationCheck } from "./types";

/**
 * Deterministic citation check. Keep the bracket rule aligned with
 * pipeline/evals/rag/citations.py.
 *
 * This function does not rewrite the answer. Invalid citations stay visible
 * to the caller so unsupported prose is not left standing without its cites.
 */
const CITE_RE = /\[([A-Za-z0-9][A-Za-z0-9._/-]{2,})\]/g;

export function extractCitedCaseIds(text: string): string[] {
  const ids: string[] = [];
  for (const match of text.matchAll(CITE_RE)) {
    ids.push(match[1].toUpperCase());
  }
  return [...new Set(ids)];
}

export function validateCitations(
  answer: string,
  allowedCaseIds: Iterable<string>,
  options?: { excludedCaseIds?: Iterable<string>; sourceOnlyIds?: Iterable<string> },
): CitationCheck {
  const cited = extractCitedCaseIds(answer);
  const allowed = new Set([...allowedCaseIds].map((id) => id.toUpperCase()).filter(Boolean));
  const excluded = new Set([...(options?.excludedCaseIds ?? [])].map((id) => id.toUpperCase()));
  const sourceOnly = new Set([...(options?.sourceOnlyIds ?? [])].map((id) => id.toUpperCase()));

  const invalid: string[] = [];
  const reasons: string[] = [];

  for (const id of cited) {
    if (excluded.has(id)) {
      invalid.push(id);
      reasons.push(`${id}: excluded or flagged`);
      continue;
    }
    if (sourceOnly.has(id) && !allowed.has(id)) {
      invalid.push(id);
      reasons.push(`${id}: source-only record cited as an incident`);
      continue;
    }
    if (!allowed.has(id)) {
      invalid.push(id);
      reasons.push(`${id}: not in retrieved evidence`);
    }
  }

  return { ok: invalid.length === 0, cited, invalid, reasons };
}
