import "server-only";
import { siteConfig } from "@/site.config";
import { suggestPlaces } from "@/lib/places";
import { CAUSES, RECORD_TYPES, type AskResult, type Cause, type RecordType } from "@/lib/types";
import { anthropic, hasAI, logUsage } from "./client";

/**
 * "Ask in plain English": turn a question into structured map filters.
 * Claude only translates the question into filters — it never answers from its own knowledge,
 * so results always come from our database.
 */

interface Parsed {
  place: string | null;
  radius_m: number | null;
  record_types: RecordType[] | null;
  causes: Cause[] | null;
  year_from: number | null;
  year_to: number | null;
  include_natural: boolean | null;
}

const SYSTEM = `You convert a user's search question about New Mexico property history into JSON filters for a map.
Only extract what the question states. Never invent places or dates. The current year is ${new Date().getFullYear()}.
- place: a place, neighborhood, street or address in New Mexico mentioned in the question, as a geocodable string with the city (e.g. "Old Town, Albuquerque"). null if none.
- radius_m: search radius in meters if stated or implied ("near" ≈ 500, "around" ≈ 1000, a whole town ≈ 4000). null if not stated.
- record_types: subset of ${JSON.stringify(RECORD_TYPES)}. "deaths"/"muertes" → death; "fires"/"incendios" → fire AND cause fire; "meth lab"/"drug lab" → drug_lab; "flood" → flood_zone; "car crash"/"traffic"/"highway" deaths → road_death. null if not stated.
- causes: subset of ${JSON.stringify(CAUSES)}. null if not stated.
- year_from / year_to: integer years. "before 1950" → year_to 1949. "in the last 10 years" → year_from current year minus 10. "1930s" → 1930..1939.
- include_natural: true only if the question asks about natural deaths or "all deaths".
The question may be in English or Spanish.`;

const TOOL = {
  name: "set_filters",
  description: "Set the map filters extracted from the question.",
  input_schema: {
    type: "object" as const,
    properties: {
      place: { type: ["string", "null"] },
      radius_m: { type: ["integer", "null"] },
      record_types: { type: ["array", "null"], items: { type: "string", enum: RECORD_TYPES } },
      causes: { type: ["array", "null"], items: { type: "string", enum: CAUSES } },
      year_from: { type: ["integer", "null"] },
      year_to: { type: ["integer", "null"] },
      include_natural: { type: ["boolean", "null"] },
    },
    required: ["place", "radius_m", "record_types", "causes", "year_from", "year_to", "include_natural"],
  },
};

async function parseWithClaude(q: string): Promise<Parsed> {
  const model = siteConfig.ai.models.fast;
  const msg = await anthropic().messages.create({
    model,
    max_tokens: 300,
    system: [{ type: "text", text: SYSTEM, cache_control: { type: "ephemeral" } }],
    tools: [TOOL],
    tool_choice: { type: "tool", name: "set_filters" },
    messages: [{ role: "user", content: q.slice(0, 400) }],
  });
  await logUsage("ask", model, msg.usage);
  const block = msg.content.find((b) => b.type === "tool_use");
  if (!block || block.type !== "tool_use") throw new Error("no tool_use");
  return block.input as Parsed;
}

/** Deterministic fallback when no API key is configured, and a sanity layer on Claude output. */
export function parseWithRules(qRaw: string): Parsed {
  const q = qRaw.toLowerCase();
  const year = new Date().getFullYear();
  const out: Parsed = {
    place: null, radius_m: null, record_types: null, causes: null, year_from: null, year_to: null, include_natural: null,
  };

  const types = new Set<RecordType>();
  const causes = new Set<Cause>();
  if (/\b(fires?|incendios?)\b/.test(q)) { types.add("fire"); types.add("death"); causes.add("fire"); }
  if (/\b(meth|drug)\s*labs?\b|laboratorio/.test(q)) types.add("drug_lab");
  if (/\bflood|inundaci/.test(q)) types.add("flood_zone");
  if (/\b(car|traffic|road|highway|crash(es)?|wrecks?|choques?|tr[aá]nsito|carretera)\b/.test(q)) types.add("road_death");
  if (/\b(deaths?|died|muertes?|muri[oó])\b/.test(q)) types.add("death");
  if (/\b(murders?|homicides?|homicidios?|shootings?|asesinat)/.test(q)) causes.add("homicide");
  if (/\b(accidents?|accidentes?|crash|drown)/.test(q)) causes.add("accident");
  if (/\bnatural/.test(q)) { causes.add("natural"); out.include_natural = true; }
  if (types.size) out.record_types = [...types];
  if (causes.size) out.causes = [...causes];

  let m: RegExpMatchArray | null;
  if ((m = q.match(/\b(?:before|antes de)\s+(\d{4})/))) out.year_to = Number(m[1]) - 1;
  if ((m = q.match(/\b(?:after|since|despu[eé]s de|desde)\s+(\d{4})/))) out.year_from = Number(m[1]);
  if ((m = q.match(/\b(\d{4})\s*(?:-|to|–|a|hasta)\s*(\d{4})/))) { out.year_from = Number(m[1]); out.year_to = Number(m[2]); }
  if ((m = q.match(/\b(1[89]\d0|20[0-2]0)'?s\b/))) { out.year_from = Number(m[1]); out.year_to = Number(m[1]) + 9; }
  if ((m = q.match(/\b(?:last|past|[uú]ltimos)\s+(\d{1,3})\s+(?:years|años)/))) out.year_from = year - Number(m[1]);
  if ((m = q.match(/\bin\s+(1[89]\d\d|20\d\d)\b/)) && out.year_from == null) { out.year_from = Number(m[1]); out.year_to = Number(m[1]); }

  if (/\bnear|cerca/.test(q)) out.radius_m = 500;

  // Place: whatever follows "in/near/around/en/cerca de", minus time phrases
  const pm = qRaw.match(/\b(?:in|near|around|at|en|cerca de|alrededor de)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ0-9 .'-]+?)(?:\s+(?:before|after|since|in the|in \d|during|last|past|from|antes|despu|desde|en los|en \d|[uú]ltimos)\b|[?,.!]|$)/i);
  if (pm) {
    const place = pm[1].trim();
    if (place && !/^\d{4}$/.test(place) && !/^(the )?(last|past)/i.test(place)) out.place = place;
  }
  return out;
}

export async function ask(q: string): Promise<AskResult> {
  let parsed: Parsed;
  let via: AskResult["via"] = "rules";
  if (hasAI() && siteConfig.ai.features.ask) {
    try {
      parsed = await parseWithClaude(q);
      via = "claude";
    } catch (e) {
      console.error("[ask] claude failed, using rules", e);
      parsed = parseWithRules(q);
    }
  } else {
    parsed = parseWithRules(q);
  }

  let place = null;
  if (parsed.place) {
    try {
      const hits = await suggestPlaces(parsed.place, 1);
      place = hits[0] ?? null;
    } catch {
      place = null;
    }
  }

  const clampYear = (y: number | null) => (y == null ? null : Math.max(siteConfig.timeline.startYear, Math.min(new Date().getFullYear(), Math.round(y))));
  return {
    place,
    radiusM: parsed.radius_m ?? (place && place.kind === "area" ? 4000 : place ? 500 : null),
    recordTypes: parsed.record_types?.filter((t) => RECORD_TYPES.includes(t)) ?? null,
    causes: parsed.causes?.filter((c) => CAUSES.includes(c)) ?? null,
    yearFrom: clampYear(parsed.year_from),
    yearTo: clampYear(parsed.year_to),
    includeNatural: parsed.include_natural,
    via,
  };
}
