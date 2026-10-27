import "server-only";
import { repo } from "@/lib/data";
import { scrubNames } from "@/lib/scrub/names";
import { siteConfig } from "@/site.config";
import type { CheckItem } from "@/lib/types";

/**
 * Adds the one-line description to list items, so a tap on a town or a spot shows what each death
 * was without opening every record. Off while features.paywall is on (summaries are then part of the
 * paid record card). Every summary goes through the name scrubber, same as /api/events/[id].
 */
export async function withPreviews(items: CheckItem[], locale: string): Promise<CheckItem[]> {
  if (siteConfig.features.paywall || items.length === 0) return items;
  try {
    const sums = await repo().eventSummaries(items.map((i) => i.id), locale);
    return items.map((i) => {
      const raw = sums[i.id];
      return raw ? { ...i, summary: scrubNames(raw).text } : i;
    });
  } catch (e) {
    console.error("[previews]", e);
    return items; // the list still works without descriptions
  }
}
