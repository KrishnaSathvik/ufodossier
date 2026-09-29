import Anthropic from "@anthropic-ai/sdk";
import type { RagGenerationResult, RagUsage } from "./types";

const client = new Anthropic();

export async function generateAnthropic(args: {
  model: string;
  system: string;
  user: string;
}): Promise<RagGenerationResult> {
  const started = Date.now();
  const stream = client.messages.stream({
    model: args.model,
    max_tokens: 1024,
    system: args.system,
    messages: [{ role: "user", content: args.user }],
  });

  let text = "";
  for await (const event of stream) {
    if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
      text += event.delta.text;
    }
  }
  const finalMessage = await stream.finalMessage();
  if (!text) {
    text = finalMessage.content
      .filter((block) => block.type === "text")
      .map((block) => block.text)
      .join("");
  }

  const usage: RagUsage = {
    inputTokens: finalMessage.usage?.input_tokens,
    outputTokens: finalMessage.usage?.output_tokens,
  };
  const thinking = (finalMessage.usage as { output_tokens_details?: { thinking_tokens?: number } } | undefined)
    ?.output_tokens_details?.thinking_tokens;
  if (typeof thinking === "number") usage.reasoningTokens = thinking;

  return {
    provider: "anthropic",
    model: finalMessage.model || args.model,
    text,
    usage,
    latencyMs: Date.now() - started,
  };
}
