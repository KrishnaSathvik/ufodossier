import type { RagAttemptRole, RagProvider } from "./types";

export type RagConfig = {
  provider: RagProvider;
  model: string;
  reasoningEffort?: string;
  evidenceSource: "vector" | "local";
};

export type RagAttempt = {
  role: RagAttemptRole;
  provider: RagProvider;
  model: string;
  reasoningEffort?: string;
};

const HISTORICAL_ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929";
const PROVIDER_FAILOVER_MODEL = "claude-sonnet-5-5";
const SELECTED_OPENAI_MODEL = "gpt-6-sol";

/**
 * Runtime selection is entirely environment-driven.
 * The unset default stays on the historical Anthropic model so an accidental
 * process start cannot flip production Ask to GPT-6.
 *
 * After RAG_PROVIDER=openai, the chain is the V2 eval decision:
 * gpt-6-sol at medium, then the same model at low, then Claude Sonnet 5.5
 * if OpenAI itself fails. Low is a cost and latency retry, not a second vendor.
 */
export function getRagConfig(): RagConfig {
  const primary = getRagAttempts()[0];
  return {
    provider: primary.provider,
    model: primary.model,
    reasoningEffort: primary.reasoningEffort,
    evidenceSource: evidenceSource(),
  };
}

export function getRagAttempts(): RagAttempt[] {
  const providerRaw = (process.env.RAG_PROVIDER ?? "anthropic").toLowerCase();
  if (providerRaw !== "openai") {
    return [
      {
        role: "primary",
        provider: "anthropic",
        model:
          process.env.ANTHROPIC_RAG_MODEL ??
          process.env.RAG_MODEL ??
          HISTORICAL_ANTHROPIC_MODEL,
      },
    ];
  }

  const primary: RagAttempt = {
    role: "primary",
    provider: "openai",
    model: process.env.RAG_MODEL ?? SELECTED_OPENAI_MODEL,
    reasoningEffort: process.env.RAG_REASONING_EFFORT ?? "medium",
  };
  const attempts: RagAttempt[] = [primary];

  const degradedModel = process.env.RAG_FALLBACK_MODEL ?? primary.model;
  const degradedEffort = process.env.RAG_FALLBACK_REASONING_EFFORT ?? "low";
  if (degradedModel !== primary.model || degradedEffort !== primary.reasoningEffort) {
    attempts.push({
      role: "degraded",
      provider: "openai",
      model: degradedModel,
      reasoningEffort: degradedEffort,
    });
  }

  const secondary = (process.env.RAG_SECONDARY_PROVIDER ?? "anthropic").toLowerCase();
  if (secondary === "anthropic") {
    attempts.push({
      role: "provider_failover",
      provider: "anthropic",
      model: process.env.ANTHROPIC_RAG_MODEL ?? PROVIDER_FAILOVER_MODEL,
    });
  }

  return attempts;
}

function evidenceSource(): "vector" | "local" {
  return (process.env.RAG_EVIDENCE_SOURCE ?? "vector").toLowerCase() === "local" ? "local" : "vector";
}
