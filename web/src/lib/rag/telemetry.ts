import { appendFileSync, mkdirSync } from "fs";
import path from "path";
import type { AskTelemetry } from "./types";

const USD_PER_MILLION: Record<string, { input: number; output: number }> = {
  "claude-sonnet-4-5-20250929": { input: 3, output: 15 },
  "claude-sonnet-5-5": { input: 2, output: 10 },
  "gpt-6-sol": { input: 2, output: 10 },
};

export function estimateCostUsd(model: string, inputTokens?: number, outputTokens?: number): number | null {
  const rate = USD_PER_MILLION[model];
  if (!rate || inputTokens == null || outputTokens == null) return null;
  return (inputTokens * rate.input + outputTokens * rate.output) / 1_000_000;
}

/**
 * Local JSONL only, unless RAG_TELEMETRY_SINK=supabase is set explicitly.
 * This milestone does not write ask_log rows to production.
 */
export async function recordTelemetry(entry: AskTelemetry, persistRemote?: () => Promise<void>): Promise<void> {
  const sink = (process.env.RAG_TELEMETRY_SINK ?? "local").toLowerCase();
  // Vercel (and similar) filesystems are read-only outside /tmp — skip local JSONL there.
  const canWriteLocal = !process.env.VERCEL && !process.env.AWS_LAMBDA_FUNCTION_NAME;
  if ((sink === "local" || sink === "both") && canWriteLocal) {
    try {
      const dir = path.resolve(process.cwd(), "../pipeline/reports/rag_telemetry");
      mkdirSync(dir, { recursive: true });
      appendFileSync(path.join(dir, "ask.jsonl"), `${JSON.stringify({ ...entry, at: new Date().toISOString() })}\n`);
    } catch (error) {
      console.warn("[ask] local telemetry write skipped:", (error as Error).message);
    }
  }
  if ((sink === "supabase" || sink === "both") && persistRemote) {
    await persistRemote();
  }
}
