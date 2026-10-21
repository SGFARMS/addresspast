import "server-only";
import { SEED_RECORDS, combineConfidence } from "@/data/seed-records";
import { distanceM, inBbox } from "@/lib/geo";
import { passesFilters } from "@/lib/filters";
import type { AreaStats, CheckItem, Coverage, EventDetail, FreeCheck, MapEvent } from "@/lib/types";
import type { Repo } from "./repo";

/** In-memory backend over the fake seed records. Used when Supabase env vars are absent. */

const events = SEED_RECORDS.map((r) => ({
  ...r,
  confidence: combineConfidence(r.sources.map((s) => s.confidence)),
  sourceCount: new Set(r.sources.map((s) => s.name)).size,
}));

const waitlist = new Set<string>();
const summaries = new Map<string, { body: string; statsHash: string }>();

function coverageFor(county: string | null): Coverage | null {
  if (!county) return null;
  const rows = events.filter((e) => e.county.toLowerCase() === county.toLowerCase());
  if (!rows.length) return null;
  const years = rows.map((r) => r.year);
  return {
    county,
    firstYear: Math.min(...years),
    lastYear: Math.max(...years),
    sourceCount: new Set(rows.flatMap((r) => r.sources.map((s) => s.name))).size,
    gapEraRecords: rows.filter((r) => r.year >= 1964 && r.year <= 2010).length,
  };
}

function item(e: (typeof events)[number], d: number): CheckItem {
  return {
    id: e.id,
    year: e.year,
    datePrecision: e.datePrecision,
    recordType: e.recordType,
    cause: e.cause,
    precision: e.precision,
    verified: e.verified,
    distanceM: Math.round(d),
  };
}

export const demoRepo: Repo = {
  kind: "demo",

  async freeCheck({ lat, lng, city, nearM, recordTypes }) {
    const visible = events.filter((e) => recordTypes.includes(e.recordType));
    const withD = visible.map((e) => ({ e, d: distanceM(lat, lng, e.lat, e.lng) }));
    const at = withD.filter(({ e, d }) => e.precision === "street" && d <= 25);
    const atIds = new Set(at.map(({ e }) => e.id));
    const near = withD
      .filter(({ e, d }) => e.precision !== "city" && d <= nearM && !atIds.has(e.id))
      .sort((a, b) => a.d - b.d);
    const nearestCounty =
      withD.sort((a, b) => a.d - b.d).find(({ d }) => d < 30000)?.e.county ?? null;
    const result: FreeCheck = {
      parcelMatched: false,
      atAddress: at.map(({ e, d }) => item(e, d)).sort((a, b) => (a.year ?? 0) - (b.year ?? 0)),
      nearby: near.map(({ e, d }) => item(e, d)),
      cityOnlyCount: city
        ? visible.filter((e) => e.precision === "city" && e.city.toLowerCase() === city.toLowerCase()).length
        : 0,
      coverage: coverageFor(nearestCounty),
      asOf: "2026-10-21T00:00:00Z",
    };
    return result;
  },

  async mapEvents(bbox, f) {
    return events
      .filter((e) => e.precision !== "city" && inBbox(e.lng, e.lat, bbox) && passesFilters(e, f))
      .map<MapEvent>((e) => ({
        id: e.id,
        lng: e.lng,
        lat: e.lat,
        recordType: e.recordType,
        cause: e.cause,
        year: e.year,
        precision: e.precision,
        confidence: e.confidence,
        verified: e.verified,
        sourceCount: e.sourceCount,
      }));
  },

  async cityDecades(f) {
    const buckets = new Map<string, { county: string; city: string; decade: number; n: number; lats: number[]; lngs: number[] }>();
    for (const e of events) {
      if (e.precision !== "city" || !passesFilters(e, f)) continue;
      const decade = Math.floor(e.year / 10) * 10;
      const key = `${e.city}|${decade}`;
      const b = buckets.get(key) ?? { county: e.county, city: e.city, decade, n: 0, lats: [], lngs: [] };
      b.n++;
      b.lats.push(e.lat);
      b.lngs.push(e.lng);
      buckets.set(key, b);
    }
    return [...buckets.values()].map((b) => ({
      county: b.county,
      city: b.city,
      decade: b.decade,
      n: b.n,
      lat: b.lats.reduce((a, c) => a + c, 0) / b.lats.length,
      lng: b.lngs.reduce((a, c) => a + c, 0) / b.lngs.length,
    }));
  },

  async eventDetail(id, full, locale) {
    const e = events.find((x) => x.id === id);
    if (!e) return null;
    const detail: EventDetail = {
      id: e.id,
      year: e.year,
      datePrecision: e.datePrecision,
      recordType: e.recordType,
      cause: e.cause,
      precision: e.precision,
      confidence: e.confidence,
      verified: e.verified,
      city: e.city,
      county: e.county,
      sourceCount: e.sourceCount,
      summary: full ? (locale === "es" ? e.summaryEs : e.summary) : null,
      sources: e.sources.map((s) => ({
        name: s.name,
        published: s.published,
        url: full ? s.url : null,
        isLocScan: s.url.includes("loc.gov"),
      })),
    };
    return detail;
  },

  async areaStats(county, city, includeNatural) {
    const rows = events.filter(
      (e) =>
        e.county.toLowerCase() === county.toLowerCase() &&
        (!city || e.city.toLowerCase() === city.toLowerCase()) &&
        (includeNatural || e.cause !== "natural"),
    );
    const count = (key: (e: (typeof rows)[number]) => string) =>
      rows.reduce<Record<string, number>>((acc, e) => ((acc[key(e)] = (acc[key(e)] ?? 0) + 1), acc), {});
    const stats: AreaStats = {
      total: rows.length,
      byDecade: count((e) => String(Math.floor(e.year / 10) * 10)),
      byCause: count((e) => e.cause),
      byPrecision: count((e) => e.precision),
      verified: rows.filter((e) => e.verified).length,
      coverage: coverageFor(county),
    };
    return stats;
  },

  async addToWaitlist({ email }) {
    const key = email.toLowerCase();
    if (waitlist.has(key)) return "exists";
    waitlist.add(key);
    return "ok";
  },

  async getAreaSummary(county, city, locale) {
    return summaries.get(`${county}|${city}|${locale}`) ?? null;
  },

  async saveAreaSummary(row) {
    summaries.set(`${row.county}|${row.city}|${row.locale}`, { body: row.body, statsHash: row.statsHash });
  },

  async logScrubHits(hits) {
    if (hits.length) console.warn("[scrub] name-like strings removed:", hits.map((h) => h.matchedText));
  },

  async logAiUsage(u) {
    console.info(`[ai] ${u.feature} ${u.model} in=${u.inputTokens} out=${u.outputTokens} $${u.costUsd.toFixed(5)}`);
  },
};
