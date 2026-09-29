export type RagProvider = "openai" | "anthropic";

export type RagAttemptRole = "primary" | "degraded" | "provider_failover";

export type CitationValidationStatus = "valid" | "repaired" | "abstained";

export type RagUsage = {
  inputTokens?: number;
  outputTokens?: number;
  reasoningTokens?: number;
};

export type RagGenerationResult = {
  provider: RagProvider;
  model: string;
  reasoningEffort?: string;
  attemptRole?: RagAttemptRole;
  text: string;
  usage: RagUsage;
  latencyMs: number;
};

export type RetrievedFile = {
  id: string;
  title: string;
  agency: string;
  kind: string;
  note: string | null;
  href: string;
};

export type RetrievedIncident = {
  id: string;
  slug: string | null;
  case_id: string;
  title: string;
  summary: string;
  raw_excerpt: string;
  occurred_at: string | null;
  location_text: string | null;
  branch: string | null;
  resolution_status: string | null;
  identity?: CanonicalContext | null;
  similarity?: number;
  lexicalScore?: number;
};

export type CanonicalContext = {
  eventId: string;
  eventLabel: string;
  memberCaseIds: string[];
  sourceRoles: { filename: string; role: string }[];
  seriesId?: string;
  seriesLabel?: string;
  seriesEventCount?: number;
};

export type CitationCheck = {
  ok: boolean;
  cited: string[];
  invalid: string[];
  reasons: string[];
};

export type RagStreamEvent =
  | { type: "text"; text: string }
  | { type: "replace"; text: string }
  | {
      type: "citations";
      citations: {
        id: string;
        slug: string | null;
        case_id: string;
        title: string;
        occurred_at: string | null;
        location_text: string | null;
      }[];
    }
  | { type: "citation_status"; status: CitationValidationStatus; invalid?: string[] }
  | { type: "slug"; slug: string }
  | { type: "error"; text: string };

export type AskTelemetry = {
  provider: RagProvider;
  model: string;
  reasoningEffort?: string;
  attemptRole?: RagAttemptRole;
  promptVersion: string;
  retrievalVersion: string;
  question: string;
  retrievedIncidentIds: string[];
  citedIncidentIds: string[];
  citationValidationStatus: CitationValidationStatus;
  inputTokens?: number;
  outputTokens?: number;
  reasoningTokens?: number;
  retrievalLatencyMs: number;
  generationLatencyMs: number;
  totalLatencyMs: number;
  estimatedCostUsd: number | null;
};
