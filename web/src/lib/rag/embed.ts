const DB_VECTOR_DIM = 1536;
const VOYAGE_DIM = 1024;

function embeddingSettings(): { provider: "voyage"; model: "voyage-3" } {
  const provider = (process.env.EMBEDDING_PROVIDER ?? "voyage").toLowerCase();
  const model = process.env.EMBEDDING_MODEL ?? "voyage-3";
  if (provider !== "voyage" || model !== "voyage-3") {
    throw new Error(
      `EMBEDDING_PROVIDER=${provider} EMBEDDING_MODEL=${model} does not match the voyage-3 index. OpenAI embeddings will not be used as a fallback.`,
    );
  }
  if (!process.env.VOYAGE_API_KEY) {
    throw new Error("VOYAGE_API_KEY is missing. Retrieval will not switch to OpenAI embeddings.");
  }
  return { provider: "voyage", model: "voyage-3" };
}

async function embedOnce(text: string): Promise<number[]> {
  embeddingSettings();
  const response = await fetch("https://api.voyageai.com/v1/embeddings", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.VOYAGE_API_KEY}`,
    },
    body: JSON.stringify({
      input: [text.slice(0, 8000)],
      model: "voyage-3",
      output_dimension: VOYAGE_DIM,
    }),
  });
  const payload = await response.json();
  if (!response.ok || !payload.data?.[0]?.embedding) {
    throw new Error(
      `Voyage embeddings failed (${response.status}). Not switching providers. ${JSON.stringify(payload).slice(0, 200)}`,
    );
  }
  const vec = payload.data[0].embedding as number[];
  if (vec.length !== VOYAGE_DIM) {
    throw new Error(`voyage-3 returned ${vec.length} dimensions, expected ${VOYAGE_DIM}`);
  }
  while (vec.length < DB_VECTOR_DIM) vec.push(0);
  return vec;
}

export async function embedQuestion(text: string): Promise<number[]> {
  try {
    return await embedOnce(text);
  } catch (error) {
    console.warn("[ask] embed first attempt failed, retrying in 500ms:", (error as Error).message);
    await new Promise((resolve) => setTimeout(resolve, 500));
    return await embedOnce(text);
  }
}
