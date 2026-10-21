import "server-only";
import { createHash } from "node:crypto";
import { siteConfig } from "@/site.config";
import { repo } from "@/lib/data";
import { scrubNames } from "@/lib/scrub/names";
import type { AreaStats } from "@/lib/types";
import { anthropic, hasAI, logUsage } from "./client";

/**
 * Short overview for county/city pages, written ONLY from aggregate stats
 * (counts by decade/cause, coverage). Claude never sees individual records here.
 */

export function statsHash(stats: AreaStats) {
  return createHash("sha1").update(JSON.stringify(stats)).digest("hex").slice(0, 16);
}

function fallback(area: string, stats: AreaStats, locale: string) {
  const decades = Object.keys(stats.byDecade).map(Number).sort((a, b) => a - b);
  const first = decades[0];
  const last = decades[decades.length - 1];
  if (locale === "es") {
    if (!stats.total) return `Todavía no hay registros públicos de ${area} en nuestras fuentes.`;
    return `Nuestras fuentes incluyen ${stats.total} registros reportados en ${area}, de la década de ${first} a la de ${last}. La cobertura entre 1964 y 2010 es limitada, así que la ausencia de registros no significa que no haya pasado nada.`;
  }
  if (!stats.total) return `We don't have any public records for ${area} in our sources yet.`;
  return `Our sources include ${stats.total} reported records in ${area}, from the ${first}s to the ${last}s. Newspaper coverage between 1964 and 2010 is thin, so a gap in records doesn't mean nothing happened.`;
}

export async function getAreaSummary(args: {
  county: string;
  city: string | null;
  area: string;
  stats: AreaStats;
  locale: string;
  generate?: boolean;
}): Promise<string> {
  const { county, city, area, stats, locale } = args;
  const hash = statsHash(stats);
  const cached = await repo().getAreaSummary(county, city ?? "", locale);
  if (cached && cached.statsHash === hash) return cached.body;
  if (!args.generate || !hasAI() || !siteConfig.ai.features.areaSummary) return cached?.body ?? fallback(area, stats, locale);

  const model = siteConfig.ai.models.fast;
  const msg = await anthropic().messages.create({
    model,
    max_tokens: 260,
    system: [
      {
        type: "text",
        cache_control: { type: "ephemeral" },
        text: `You write a calm, factual 2–3 sentence overview for a property-history page.
Use ONLY the JSON stats provided. Do not mention or invent any specific incident, person, address, or name.
Mention the decades covered and the most common categories in plain words. Always note that 1964–2010 coverage is thin and that "no records" never means "nothing happened."
No sensational words ("murder house", "haunted", "grisly"). Write in ${locale === "es" ? "Spanish" : "English"}.`,
      },
    ],
    messages: [{ role: "user", content: `Area: ${area}, New Mexico\nStats: ${JSON.stringify(stats)}` }],
  });
  await logUsage("area_summary", model, msg.usage);
  const text = msg.content.map((b) => (b.type === "text" ? b.text : "")).join("").trim();
  const body = scrubNames(text).text || fallback(area, stats, locale);
  await repo().saveAreaSummary({ county, city: city ?? "", locale, body, statsHash: hash, model });
  return body;
}
