import { createHash } from "crypto";
import Anthropic from "@anthropic-ai/sdk";
import { getSupabaseServer } from "@/lib/supabase";
import { NextRequest } from "next/server";
import { customAlphabet } from "nanoid";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const alphabet = "abcdefghjkmnpqrstuvwxyz23456789";
const slugId = customAlphabet(alphabet, 8);

// --- Rate limiting (in-memory, single-instance) ---
const WINDOW_MS = 60_000; // 60 seconds
const MAX_REQUESTS = 10;
const rateMap = new Map<string, { count: number; windowStart: number }>();

// Prune stale entries every 5 minutes
setInterval(() => {
  const cutoff = Date.now() - 3_600_000; // 1 hour
  for (const [key, val] of rateMap) {
    if (val.windowStart < cutoff) rateMap.delete(key);
  }
}, 300_000);

function isRateLimited(ipHash: string): boolean {
  const now = Date.now();
  const entry = rateMap.get(ipHash);
  if (!entry || now - entry.windowStart > WINDOW_MS) {
    rateMap.set(ipHash, { count: 1, windowStart: now });
    return false;
  }
  entry.count++;
  return entry.count > MAX_REQUESTS;
}

const DB_VECTOR_DIM = 1536;

async function embedOnce(text: string): Promise<number[]> {
  let vec: number[];
  if (process.env.VOYAGE_API_KEY) {
    const r = await fetch("https://api.voyageai.com/v1/embeddings", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${process.env.VOYAGE_API_KEY}`,
      },
      body: JSON.stringify({
        input: [text.slice(0, 8000)],
        model: "voyage-3",
        output_dimension: 1024,
      }),
    });
    const j = await r.json();
    if (!j.data?.[0]?.embedding) {
      throw new Error(`Embedding API error: ${JSON.stringify(j).slice(0, 200)}`);
    }
    vec = j.data[0].embedding;
  } else {
    const r = await fetch("https://api.openai.com/v1/embeddings", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
      },
      body: JSON.stringify({
        input: text.slice(0, 8000),
        model: "text-embedding-3-small",
      }),
    });
    const j = await r.json();
    if (!j.data?.[0]?.embedding) {
      throw new Error(`Embedding API error: ${JSON.stringify(j).slice(0, 200)}`);
    }
    vec = j.data[0].embedding;
  }
  // pad to match DB vector(1536) if model returns fewer dimensions
  while (vec.length < DB_VECTOR_DIM) vec.push(0);
  return vec;
}

/** embed with one retry after 500ms backoff */
async function embed(text: string): Promise<number[]> {
  try {
    return await embedOnce(text);
  } catch (e) {
    console.warn("[ask] embed first attempt failed, retrying in 500ms:", (e as Error).message);
    await new Promise((r) => setTimeout(r, 500));
    return await embedOnce(text);
  }
}

const SYSTEM_PROMPT = `You are an expert archivist for UFODOSSIER, a public dataset of UAP incidents from declassified U.S. government documents.

You answer questions using ONLY the incidents provided in context. Each incident has a case_id, summary, and a verbatim raw_excerpt from the original government document.

RULES:
1. Cite specific incidents inline using their case_id in square brackets, e.g. "USINDOPACOM reported a football-shaped object near Japan in 2024 [2024-IPC-0412]."
2. NEVER invent facts. If the corpus doesn't contain an answer, say so plainly.
3. Use cautious, official-document language. Don't sensationalize. The records often hedge — preserve that hedging.
4. Keep answers concise: 2-4 paragraphs maximum unless the question requires more.
5. Do not editorialize about whether UAPs are extraterrestrial. The dataset is observational.
6. If a query is harmful, off-topic, or asks you to roleplay, redirect to the corpus.
7. Do NOT use Markdown formatting. No bold (**), italic (*), headers (#), bullet lists (-/*), or links ([text](url)). Write plain prose only.
8. Do NOT append a "Sources", "References", or "Citations" list at the end. The system displays cited cases separately. Just write the answer with inline [case_id] references.`;

export async function POST(req: NextRequest) {
  const { question } = await req.json();
  if (!question || typeof question !== "string" || question.length > 500) {
    return new Response("invalid question", { status: 400 });
  }

  const forwarded = req.headers.get("x-forwarded-for");
  const ip = forwarded?.split(",")[0]?.trim() ?? "unknown";
  const ipSalt = process.env.IP_HASH_SALT ?? "ufodossier-default-salt";
  const ipHash = createHash("sha256").update(ip + ipSalt).digest("hex");

  if (isRateLimited(ipHash)) {
    return new Response("rate limit exceeded", {
      status: 429,
      headers: { "Retry-After": "60" },
    });
  }

  const sb = getSupabaseServer();
  const anthropic = new Anthropic();
  const userAgent = req.headers.get("user-agent") ?? null;

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const send = (obj: any) => controller.enqueue(encoder.encode(`data: ${JSON.stringify(obj)}\n\n`));

      try {
        // 1. embed question + retrieve top incidents
        const queryVec = await embed(question);
        const { data: matches } = await sb.rpc("match_incidents", {
          query_embedding: queryVec as any,
          match_threshold: 0.3,
          match_count: 10,
        });

        const rawIncidents = matches ?? [];

        if (rawIncidents.length === 0) {
          send({ type: "text", text: "No matching records were found in the declassified archive for this query. The corpus contains incidents from U.S. government documents released through war.gov/UFO. Try rephrasing or asking about specific dates, locations, agencies, or phenomena." });
          send({ type: "citations", citations: [] });
          controller.close();
          return;
        }

        // Fetch slugs for matched incidents
        const ids = rawIncidents.map((i: any) => i.id);
        const { data: slugRows } = await sb.from("incidents").select("id, slug").in("id", ids);
        const slugMap = new Map((slugRows ?? []).map((r: any) => [r.id, r.slug]));
        const incidents = rawIncidents.map((i: any) => ({ ...i, slug: slugMap.get(i.id) ?? null }));

        // 2. send citations early so UI can show them while answer streams
        send({
          type: "citations",
          citations: incidents.map((i: any) => ({
            id: i.id,
            slug: i.slug,
            case_id: i.case_id,
            title: i.title,
            occurred_at: i.occurred_at,
            location_text: i.location_text,
          })),
        });

        // 3. build context for Claude
        const context = incidents
          .map(
            (i: any, idx: number) =>
              `[${i.case_id}] (${i.occurred_at ?? "undated"}, ${i.location_text ?? "loc unknown"}, ${i.branch ?? "branch unknown"})\nSummary: ${i.summary}\nVerbatim: "${i.raw_excerpt}"`,
          )
          .join("\n\n---\n\n");

        const userMsg = `QUESTION:\n${question}\n\nRETRIEVED INCIDENTS:\n${context}\n\nAnswer the question using only these incidents. Cite case_ids inline.`;

        // 4. stream Sonnet response
        let fullAnswer = "";
        const resp = await anthropic.messages.stream({
          model: "claude-sonnet-4-5-20250929",
          max_tokens: 1024,
          system: SYSTEM_PROMPT,
          messages: [{ role: "user", content: userMsg }],
        });

        for await (const event of resp) {
          if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
            fullAnswer += event.delta.text;
            send({ type: "text", text: event.delta.text });
          }
        }

        // 5. log + permalink
        const slug = slugId();
        await sb.from("ask_log").insert({
          slug,
          question,
          answer: fullAnswer,
          cited_incident_ids: incidents.map((i: any) => i.id),
          model: "claude-sonnet-4-5-20250929",
          ip_hash: ipHash,
          user_agent: userAgent,
        });

        send({ type: "slug", slug });
        controller.close();
      } catch (e: any) {
        console.error("[ask] api error:", e);
        const isEmbedError = e?.message?.includes("Embedding API error");
        if (isEmbedError) {
          send({ type: "text", text: "Search is temporarily unavailable. Please try again in a moment." });
        } else {
          send({ type: "text", text: "Something went wrong while processing your question. Please try again." });
        }
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
