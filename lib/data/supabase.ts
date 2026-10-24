import "server-only";
import { serviceClient } from "@/lib/supabase/server";
import type {
  AreaStats, CheckItem, CityBucket, Coverage, EventDetail, FreeCheck, MapEvent, MapFilters,
} from "@/lib/types";
import type { Repo } from "./repo";

/* eslint-disable @typescript-eslint/no-explicit-any */

function filterArgs(f: MapFilters) {
  return {
    p_record_types: f.recordTypes,
    p_causes: f.causes,
    p_include_natural: f.includeNatural,
    p_min_confidence: f.minConfidence,
    p_verified_only: f.verifiedOnly,
  };
}

function toCoverage(c: any): Coverage | null {
  if (!c) return null;
  return {
    county: c.county,
    firstYear: c.first_year ?? null,
    lastYear: c.last_year ?? null,
    sourceCount: Number(c.source_count ?? 0),
    gapEraRecords: Number(c.gap_era_records ?? 0),
  };
}

function toItem(x: any): CheckItem {
  return {
    id: x.id,
    year: x.year ?? null,
    datePrecision: x.date_precision ?? null,
    recordType: x.record_type,
    cause: x.cause,
    precision: x.precision,
    verified: Boolean(x.verified),
    distanceM: Number(x.distance_m ?? 0),
    buildingLevel: Boolean(x.building_level),
    predatesBuilding: Boolean(x.predates_building),
  };
}

async function rpc<T>(fn: string, args: Record<string, unknown>): Promise<T> {
  const { data, error } = await serviceClient().rpc(fn, args);
  if (error) throw new Error(`${fn}: ${error.message}`);
  return data as T;
}

export const supabaseRepo: Repo = {
  kind: "supabase",

  async freeCheck({ lat, lng, city, nearM, recordTypes }) {
    const d = await rpc<any>("ap_api_free_check", {
      p_lat: lat, p_lng: lng, p_city: city, p_near_m: nearM, p_record_types: recordTypes,
    });
    const r: FreeCheck = {
      parcelMatched: Boolean(d.parcel_matched),
      parcelYearBuilt: d.parcel_year_built ?? null,
      atAddress: (d.at_address ?? []).map(toItem),
      nearby: (d.nearby ?? []).map(toItem),
      cityOnlyCount: Number(d.city_only_count ?? 0),
      coverage: toCoverage(d.coverage),
      asOf: d.as_of ?? null,
    };
    return r;
  },

  async mapEvents([w, s, e, n], f) {
    const rows = await rpc<any[]>("ap_api_map_events", {
      p_west: w, p_south: s, p_east: e, p_north: n, ...filterArgs(f),
    });
    return rows.map<MapEvent>((x) => ({
      id: x.id,
      lng: x.lng,
      lat: x.lat,
      recordType: x.record_type,
      cause: x.cause,
      year: x.event_year,
      precision: x.geo_precision,
      confidence: Number(x.confidence),
      verified: x.verified,
      sourceCount: x.source_count,
    }));
  },

  async cityEvents(city, f) {
    let q = serviceClient()
      .from("ap_events")
      .select("id,event_year,date_precision,record_type,cause_category,geocode_precision,verified,building_level,confidence")
      .eq("hidden", false)
      .eq("geocode_precision", "city")
      .ilike("city", city)
      .in("record_type", f.recordTypes)
      .gte("confidence", f.minConfidence ?? 0)
      .order("event_year", { ascending: true, nullsFirst: false })
      .limit(500);
    if (f.causes) q = q.in("cause_category", f.causes);
    if (!f.includeNatural) q = q.neq("cause_category", "natural");
    if (f.verifiedOnly) q = q.eq("verified", true);
    const { data, error } = await q;
    if (error) throw new Error(`cityEvents: ${error.message}`);
    return (data ?? []).map<CheckItem>((x: any) => ({
      id: x.id, year: x.event_year, datePrecision: x.date_precision, recordType: x.record_type, cause: x.cause_category,
      precision: x.geocode_precision, verified: Boolean(x.verified), distanceM: 0,
      buildingLevel: Boolean(x.building_level), predatesBuilding: false,
    }));
  },

  async cityDecades(f) {
    const rows = await rpc<any[]>("ap_api_city_decades", filterArgs(f));
    return rows.map<CityBucket>((x) => ({
      county: x.county, city: x.city, decade: x.decade, n: Number(x.n), lng: x.lng, lat: x.lat,
    }));
  },

  async eventDetail(id, full, locale) {
    const d = await rpc<any>("ap_api_event_detail", { p_event_id: id, p_full: full, p_locale: locale });
    if (!d) return null;
    const r: EventDetail = {
      id: d.id,
      year: d.year,
      datePrecision: d.date_precision,
      recordType: d.record_type,
      cause: d.cause,
      precision: d.precision,
      confidence: Number(d.confidence),
      verified: d.verified,
      city: d.city,
      county: d.county,
      sourceCount: d.source_count,
      buildingLevel: Boolean(d.building_level),
      parcelYearBuilt: d.parcel_year_built ?? null,
      summary: d.summary ?? null,
      sources: (d.sources ?? []).map((s: any) => ({
        name: s.name, published: s.published ?? null, url: s.url ?? null, isLocScan: Boolean(s.is_loc_scan),
      })),
    };
    return r;
  },

  async requestRemoval(r) {
    const d = await rpc<any>("ap_api_request_removal", {
      p_event_id: r.eventId, p_email: r.email, p_relationship: r.relationship, p_reason: r.reason, p_details: r.details,
    });
    return { ok: Boolean(d?.ok), fastLane: Boolean(d?.fast_lane) };
  },

  async areaStats(county, city, includeNatural) {
    const d = await rpc<any>("ap_api_area_stats", { p_county: county, p_city: city, p_include_natural: includeNatural });
    const r: AreaStats = {
      total: Number(d.total ?? 0),
      byDecade: d.by_decade ?? {},
      byCause: d.by_cause ?? {},
      byPrecision: d.by_precision ?? {},
      verified: Number(d.verified ?? 0),
      coverage: toCoverage(d.coverage),
    };
    return r;
  },

  async addToWaitlist({ email, locale, county, referrer }) {
    const { error } = await serviceClient().from("ap_waitlist").insert({ email, locale, county, referrer });
    if (error?.code === "23505") return "exists";
    if (error) throw new Error(error.message);
    return "ok";
  },

  async getAreaSummary(county, city, locale) {
    const { data } = await serviceClient()
      .from("ap_area_summaries")
      .select("body, stats_hash")
      .eq("county", county)
      .eq("city", city)
      .eq("locale", locale)
      .maybeSingle();
    return data ? { body: data.body, statsHash: data.stats_hash } : null;
  },

  async saveAreaSummary(row) {
    await serviceClient().from("ap_area_summaries").upsert({
      county: row.county, city: row.city, locale: row.locale, body: row.body,
      stats_hash: row.statsHash, model: row.model, generated_at: new Date().toISOString(),
    });
  },

  async logScrubHits(hits) {
    if (!hits.length) return;
    await serviceClient().from("ap_scrub_hits").insert(
      hits.map((h) => ({
        event_id: h.eventId, field: h.field, matched_text: h.matchedText, detector: h.detector, context: h.context,
      })),
    );
  },

  async logAiUsage(u) {
    await serviceClient().from("ap_ai_usage").insert({
      feature: u.feature, model: u.model, input_tokens: u.inputTokens, output_tokens: u.outputTokens,
      cache_read_tokens: u.cacheReadTokens ?? 0, cache_write_tokens: u.cacheWriteTokens ?? 0, cost_usd: u.costUsd,
    });
  },
};
