import "server-only";
import Anthropic from "@anthropic-ai/sdk";
import { siteConfig } from "@/site.config";
import { repo } from "@/lib/data";

let client: Anthropic | null = null;

export function hasAI() {
  return Boolean(process.env.ANTHROPIC_API_KEY);
}

export function anthropic() {
  if (!client) client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  return client;
}

interface Usage {
  input_tokens?: number | null;
  output_tokens?: number | null;
  cache_read_input_tokens?: number | null;
  cache_creation_input_tokens?: number | null;
}

export function costUsd(model: string, u: Usage, batched = false) {
  const p = siteConfig.ai.pricing[model];
  if (!p) return 0;
  const m = batched ? 0.5 : 1;
  return (
    ((u.input_tokens ?? 0) * p.input +
      (u.output_tokens ?? 0) * p.output +
      (u.cache_read_input_tokens ?? 0) * p.cacheRead +
      (u.cache_creation_input_tokens ?? 0) * p.cacheWrite) *
    m /
    1_000_000
  );
}

/** Log tokens + cost per feature. Never throws. */
export async function logUsage(feature: string, model: string, u: Usage) {
  try {
    await repo().logAiUsage({
      feature,
      model,
      inputTokens: u.input_tokens ?? 0,
      outputTokens: u.output_tokens ?? 0,
      cacheReadTokens: u.cache_read_input_tokens ?? 0,
      cacheWriteTokens: u.cache_creation_input_tokens ?? 0,
      costUsd: costUsd(model, u),
    });
  } catch (e) {
    console.error("[ai] usage log failed", e);
  }
}
