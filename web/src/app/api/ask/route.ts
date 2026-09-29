import { createHash, randomBytes } from "crypto";
import { NextRequest } from "next/server";
import { buildUserMessage } from "@/lib/rag/context";
import { generateGroundedAnswer } from "@/lib/rag/generate";
import { isOffTopic, OFF_TOPIC_TEXT } from "@/lib/rag/guard";
import { RAG_PROMPT_VERSION, RETRIEVAL_VERSION } from "@/lib/rag/prompt";
import { retrieveEvidence } from "@/lib/rag/retrieve";
import { estimateCostUsd, recordTelemetry } from "@/lib/rag/telemetry";
import { getRagConfig } from "@/lib/rag/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const WINDOW_MS = 60_000;
const MAX_REQUESTS = 10;
const rateMap = new Map<string, { count: number; windowStart: number }>();

setInterval(() => {
  const cutoff = Date.now() - 3_600_000;
  for (const [key, val] of rateMap) {
    if (val.windowStart < cutoff) rateMap.delete(key);
  }
}, 300_000);

function citationsFor(
  text: string,
  citedIds: string[],
  retrieved: Awaited<ReturnType<typeof retrieveEvidence>>,
) {
  const lower = text.toLowerCase();
  const byCase = new Map(retrieved.incidents.map((incident) => [incident.case_id.toUpperCase(), incident]));
  const cases = citedIds
    .map((id) => byCase.get(id.toUpperCase()) ?? null)
    .filter((item): item is NonNullable<typeof item> => Boolean(item));
  const namedFiles = retrieved.files.filter((file) => fileUsedInAnswer(file, lower));
  let files = namedFiles.length > 0 ? namedFiles : retrieved.scope;
  if (
    files.length === 0 &&
    retrieved.files.length > 0 &&
    !/do not answer|isn't covered by the records/i.test(text)
  ) {
    files = retrieved.files
      .filter((file) =>
        /project sign|project grudge|blue book|bluebook|ruppelt|air materiel command/i.test(
          `${file.title} ${file.note ?? ""}`,
        ),
      )
      .slice(0, 4);
  }
  return [
    ...cases.map((item) => ({
      id: item.case_id,
      slug: item.slug,
      case_id: item.case_id,
      title: item.title,
      occurred_at: item.occurred_at,
      location_text: item.location_text,
      href: `/incident/${item.slug ?? item.case_id}`,
    })),
    ...files.map((file) => ({
      id: file.id,
      slug: null,
      case_id: file.id,
      title: file.title,
      occurred_at: null,
      location_text: null,
      href: file.href,
    })),
  ];
}

function fileUsedInAnswer(
  file: { id: string; title: string; note?: string | null },
  lower: string,
): boolean {
  if (lower.includes(file.id.toLowerCase())) return true;
  const title = file.title.toLowerCase();
  if (title.length > 16 && lower.includes(title.slice(0, 48))) return true;
  const blob = `${file.title} ${file.note ?? ""}`.toLowerCase();
  if (blob.includes("project sign") && /\b(project )?sign\b/.test(lower)) return true;
  if (blob.includes("project grudge") && /\bgrudge\b/.test(lower)) return true;
  if ((blob.includes("blue book") || blob.includes("bluebook")) && /blue\s*book/.test(lower)) return true;
  if (blob.includes("ruppelt") && /ruppelt/.test(lower)) return true;
  return false;
}

function isRateLimited(ipHash: string): boolean {
  const now = Date.now();
  const entry = rateMap.get(ipHash);
  if (!entry || now - entry.windowStart > WINDOW_MS) {
    rateMap.set(ipHash, { count: 1, windowStart: now });
    return false;
  }
  entry.count += 1;
  return entry.count > MAX_REQUESTS;
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);
  const question = body?.question;
  if (!question || typeof question !== "string" || question.length > 500) {
    return new Response("invalid question", { status: 400 });
  }

  const forwarded = req.headers.get("x-forwarded-for");
  const ip = forwarded?.split(",")[0]?.trim() ?? "unknown";
  const ipSalt = process.env.IP_HASH_SALT ?? "ufodossier-default-salt";
  const ipHash = createHash("sha256").update(ip + ipSalt).digest("hex");
  if (isRateLimited(ipHash)) {
    return new Response("rate limit exceeded", { status: 429, headers: { "Retry-After": "60" } });
  }

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const send = (obj: Record<string, unknown>) =>
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(obj)}\n\n`));
      const started = Date.now();
      try {
        if (isOffTopic(question)) {
          send({ type: "replace", text: OFF_TOPIC_TEXT });
          send({ type: "citations", citations: [] });
          send({ type: "citation_status", status: "abstained", invalid: [] });
          controller.close();
          return;
        }

        const retrieved = await retrieveEvidence(question);
        const generated = await generateGroundedAnswer({
          user: buildUserMessage(
            question,
            retrieved.incidents,
            retrieved.files,
            retrieved.facts,
            retrieved.scopedFiles,
            retrieved.note,
          ),
          allowedCaseIds: retrieved.allowedCaseIds,
          sourceOnlyIds: retrieved.sourceOnlyIds,
        });

        send({ type: "replace", text: generated.text });
        send({
          type: "citations",
          citations: citationsFor(generated.text, generated.cited, retrieved),
        });
        send({
          type: "citation_status",
          status: generated.status,
          invalid: generated.invalid,
        });

        const config = getRagConfig();
        const slug = randomBytes(5).toString("hex").slice(0, 8);
        const citedIds = retrieved.incidents
          .filter((incident) => generated.cited.includes(incident.case_id.toUpperCase()))
          .map((incident) => incident.id);

        await recordTelemetry({
          provider: generated.result.provider,
          model: generated.result.model,
          reasoningEffort: generated.result.reasoningEffort,
          attemptRole: generated.result.attemptRole,
          promptVersion: RAG_PROMPT_VERSION,
          retrievalVersion: config.evidenceSource === "local" ? "local-lexical-v1" : RETRIEVAL_VERSION,
          question,
          retrievedIncidentIds: retrieved.incidents.map((incident) => incident.id),
          citedIncidentIds: citedIds,
          citationValidationStatus: generated.status,
          inputTokens: generated.result.usage.inputTokens,
          outputTokens: generated.result.usage.outputTokens,
          reasoningTokens: generated.result.usage.reasoningTokens,
          retrievalLatencyMs: retrieved.latencyMs,
          generationLatencyMs: generated.result.latencyMs,
          totalLatencyMs: Date.now() - started,
          estimatedCostUsd: estimateCostUsd(
            generated.result.model,
            generated.result.usage.inputTokens,
            generated.result.usage.outputTokens,
          ),
        });

        send({ type: "slug", slug });
        controller.close();
      } catch (error) {
        console.error("[ask] api error:", error);
        const message = (error as Error).message ?? "";
        send({
          type: "text",
          text: message.includes("Embedding API error") || message.includes("Voyage embeddings failed") || message.includes("VOYAGE_API_KEY")
            ? "Search is temporarily unavailable. Please try again in a moment."
            : "Something went wrong while processing your question. Please try again.",
        });
        send({ type: "citations", citations: [] });
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
