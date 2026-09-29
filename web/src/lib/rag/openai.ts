import type { RagGenerationResult, RagUsage } from "./types";

type ResponsesEvent = {
  type?: string;
  delta?: string;
  text?: string;
  response?: {
    output_text?: string;
    usage?: {
      input_tokens?: number;
      output_tokens?: number;
      output_tokens_details?: { reasoning_tokens?: number };
    };
  };
};

export async function generateOpenAI(args: {
  model: string;
  reasoningEffort: string;
  system: string;
  user: string;
}): Promise<RagGenerationResult> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY is not configured");
  }

  const started = Date.now();
  const response = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: args.model,
      instructions: args.system,
      input: args.user,
      reasoning: { effort: args.reasoningEffort },
      max_output_tokens: 1024,
      stream: true,
    }),
  });

  if (!response.ok || !response.body) {
    const errText = await response.text().catch(() => "");
    throw new Error(`OpenAI Responses error ${response.status}: ${errText.slice(0, 400)}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let text = "";
  const usage: RagUsage = {};

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n");
    buffer = parts.pop() ?? "";
    for (const line of parts) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const payload = trimmed.slice(5).trim();
      if (!payload || payload === "[DONE]") continue;
      let event: ResponsesEvent;
      try {
        event = JSON.parse(payload) as ResponsesEvent;
      } catch {
        continue;
      }
      if (event.type === "response.output_text.delta" && typeof event.delta === "string") {
        text += event.delta;
      } else if (event.type === "response.completed" && event.response) {
        if (!text && typeof event.response.output_text === "string") {
          text = event.response.output_text;
        }
        const raw = event.response.usage;
        if (raw) {
          usage.inputTokens = raw.input_tokens;
          usage.outputTokens = raw.output_tokens;
          if (typeof raw.output_tokens_details?.reasoning_tokens === "number") {
            usage.reasoningTokens = raw.output_tokens_details.reasoning_tokens;
          }
        }
      }
    }
  }

  return {
    provider: "openai",
    model: args.model,
    reasoningEffort: args.reasoningEffort,
    text,
    usage,
    latencyMs: Date.now() - started,
  };
}
