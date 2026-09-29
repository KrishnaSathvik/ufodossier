import { generateAnthropic } from "./anthropic";
import { validateCitations } from "./citations";
import { getRagAttempts, type RagAttempt } from "./config";
import { ABSTENTION_TEXT, RAG_SYSTEM_PROMPT } from "./prompt";
import { generateOpenAI } from "./openai";
import type { CitationValidationStatus, RagGenerationResult } from "./types";

export type GeneratedAnswer = {
  result: RagGenerationResult;
  status: CitationValidationStatus;
  cited: string[];
  invalid: string[];
  text: string;
};

async function callAttempt(attempt: RagAttempt, system: string, user: string): Promise<RagGenerationResult> {
  const generated =
    attempt.provider === "openai"
      ? await generateOpenAI({
          model: attempt.model,
          reasoningEffort: attempt.reasoningEffort ?? "medium",
          system,
          user,
        })
      : await generateAnthropic({ model: attempt.model, system, user });
  return { ...generated, attemptRole: attempt.role, reasoningEffort: attempt.reasoningEffort };
}

async function answerOnAttempt(
  attempt: RagAttempt,
  args: {
    user: string;
    allowedCaseIds: string[];
    excludedCaseIds?: string[];
    sourceOnlyIds?: string[];
  },
): Promise<GeneratedAnswer> {
  const first = await callAttempt(attempt, RAG_SYSTEM_PROMPT, args.user);
  const firstCheck = validateCitations(first.text, args.allowedCaseIds, {
    excludedCaseIds: args.excludedCaseIds,
    sourceOnlyIds: args.sourceOnlyIds,
  });
  if (firstCheck.ok) {
    return { result: first, status: "valid", cited: firstCheck.cited, invalid: [], text: first.text };
  }

  const repairUser = `${args.user}

The previous draft cited identifiers that are not allowed: ${firstCheck.invalid.join(", ") || "none parsed"}.
Reasons: ${firstCheck.reasons.join("; ")}
Rewrite the answer so every [CASE-ID] appears in the case list above. Do not put a filename in brackets.
If those records do not support an answer under that constraint, say: "The records found for this question do not answer it." Do not leave unsupported claims in place.`;

  const second = await callAttempt(attempt, RAG_SYSTEM_PROMPT, repairUser);
  const secondCheck = validateCitations(second.text, args.allowedCaseIds, {
    excludedCaseIds: args.excludedCaseIds,
    sourceOnlyIds: args.sourceOnlyIds,
  });
  const usage = {
    inputTokens: sum(first.usage.inputTokens, second.usage.inputTokens),
    outputTokens: sum(first.usage.outputTokens, second.usage.outputTokens),
    reasoningTokens: sum(first.usage.reasoningTokens, second.usage.reasoningTokens),
  };
  const merged: RagGenerationResult = {
    ...second,
    usage,
    latencyMs: first.latencyMs + second.latencyMs,
  };

  if (secondCheck.ok) {
    return {
      result: merged,
      status: "repaired",
      cited: secondCheck.cited,
      invalid: firstCheck.invalid,
      text: second.text,
    };
  }

  return {
    result: merged,
    status: "abstained",
    cited: [],
    invalid: secondCheck.invalid,
    text: ABSTENTION_TEXT,
  };
}

export async function generateGroundedAnswer(args: {
  user: string;
  allowedCaseIds: string[];
  excludedCaseIds?: string[];
  sourceOnlyIds?: string[];
}): Promise<GeneratedAnswer> {
  const attempts = getRagAttempts();
  let lastError: unknown;
  for (const attempt of attempts) {
    try {
      return await answerOnAttempt(attempt, args);
    } catch (error) {
      lastError = error;
      console.error(
        `[ask] ${attempt.role} failed (${attempt.provider} ${attempt.model}${attempt.reasoningEffort ? ` ${attempt.reasoningEffort}` : ""})`,
      );
    }
  }
  throw lastError instanceof Error ? lastError : new Error("All RAG attempts failed");
}

function sum(a?: number, b?: number): number | undefined {
  if (a == null && b == null) return undefined;
  return (a ?? 0) + (b ?? 0);
}
