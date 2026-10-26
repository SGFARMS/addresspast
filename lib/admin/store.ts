import "server-only";
import { hasSupabase, serviceClient } from "@/lib/supabase/server";
import type { AdminAction, AdminQueue, ReviewDispute, ReviewIncident, ReviewSuggestion } from "./types";

/* eslint-disable @typescript-eslint/no-explicit-any */

export interface AdminStore {
  queue(): Promise<AdminQueue>;
  act(a: AdminAction): Promise<void>;
}

function must<T>({ data, error }: { data: T | null; error: { message: string } | null }, what: string): T {
  if (error) throw new Error(`${what}: ${error.message}`);
  return data as T;
}

const supabaseStore: AdminStore = {
  async queue() {
    const db = serviceClient();
    const [inc, sug, dis, incCount, evCount, spend, run] = await Promise.all([
      db.from("ap_incidents")
        .select("id,source_name,source_url,published_date,incident_date,address_raw,unit,city,county,place_kind,cause_category,summary,confidence,review_reason,geocode_status,created_at")
        .eq("needs_review", true).eq("hidden", false).order("created_at").limit(200),
      db.from("ap_location_suggestions")
        .select("id,incident_id,suggested_lat,suggested_lng,suggested_address,rationale,ap_incidents(address_raw,city,incident_year,summary,source_url)")
        .eq("status", "pending").order("created_at").limit(200),
      db.from("ap_disputes")
        .select("id,event_id,requester_email,relationship,reason,details,fast_lane,created_at,ap_events(event_year,city,cause_category,hidden)")
        .eq("status", "open").order("priority", { ascending: false }).order("created_at").limit(200),
      db.from("ap_incidents").select("id", { count: "exact", head: true }),
      db.from("ap_events").select("id", { count: "exact", head: true }).eq("hidden", false),
      db.from("ap_ai_usage").select("cost_usd").like("feature", "harvest_%").limit(100000),
      db.from("ap_pipeline_runs").select("job,status,finished_at").order("started_at", { ascending: false }).limit(1),
    ]);
    const incidents = must<any[]>(inc, "incidents").map<ReviewIncident>((r) => ({
      id: r.id, sourceName: r.source_name, sourceUrl: r.source_url, publishedDate: r.published_date,
      incidentDate: r.incident_date, addressRaw: r.address_raw, unit: r.unit, city: r.city, county: r.county,
      placeKind: r.place_kind, cause: r.cause_category, summary: r.summary,
      confidence: r.confidence == null ? null : Number(r.confidence), reviewReason: r.review_reason,
      outsideArea: r.geocode_status === "failed", createdAt: r.created_at,
    }))
      // Records we could place first; ones with no New Mexico town (El Paso, Denver...) at the end.
      .sort((a, b) => Number(a.outsideArea) - Number(b.outsideArea));
    const suggestions = must<any[]>(sug, "suggestions").map<ReviewSuggestion>((r) => ({
      id: r.id, incidentId: r.incident_id, addressRaw: r.ap_incidents?.address_raw ?? "", city: r.ap_incidents?.city ?? null,
      year: r.ap_incidents?.incident_year ?? null, summary: r.ap_incidents?.summary ?? null, sourceUrl: r.ap_incidents?.source_url ?? "",
      suggestedLat: r.suggested_lat, suggestedLng: r.suggested_lng, suggestedAddress: r.suggested_address, rationale: r.rationale,
    }));
    const disputes = must<any[]>(dis, "disputes").map<ReviewDispute>((r) => ({
      id: r.id, eventId: r.event_id, eventYear: r.ap_events?.event_year ?? null, eventCity: r.ap_events?.city ?? null,
      eventCause: r.ap_events?.cause_category ?? null, eventHidden: r.ap_events?.hidden ?? null,
      requesterEmail: r.requester_email, relationship: r.relationship, reason: r.reason, details: r.details,
      fastLane: Boolean(r.fast_lane), createdAt: r.created_at,
    }));
    const last = must<any[]>(run, "runs")[0];
    return {
      backend: "supabase",
      incidents,
      suggestions,
      disputes,
      stats: {
        incidentsTotal: incCount.count ?? 0,
        eventsVisible: evCount.count ?? 0,
        harvestSpendUsd: must<any[]>(spend, "spend").reduce((a, r) => a + Number(r.cost_usd || 0), 0),
        lastRun: last ? { job: last.job, status: last.status, finishedAt: last.finished_at } : null,
      },
    };
  },

  async act(a) {
    const db = serviceClient();
    const now = new Date().toISOString();
    if (a.type === "incident") {
      // Clearing needs_review fires ap_incidents_on_hide, which refreshes the event if there is one;
      // records without an event get one in the nightly dedupe.
      const patch = a.action === "approve" ? { needs_review: false, review_reason: null } : { hidden: true, needs_review: false };
      must(await db.from("ap_incidents").update(patch).eq("id", a.id).select("id"), "incident");
      return;
    }
    if (a.type === "suggestion") {
      const s = must<any>(await db.from("ap_location_suggestions").select("*").eq("id", a.id).single(), "suggestion");
      if (a.action === "accept") {
        const inc = must<any>(
          await db.from("ap_incidents").update({
            lat: s.suggested_lat, lng: s.suggested_lng, geocode_precision: "street_historic", geocode_status: "ok",
            geocode_source: "review", matched_address: s.suggested_address, geocoded_at: now,
          }).eq("id", s.incident_id).select("event_id").single(),
          "incident",
        );
        if (inc?.event_id) must(await db.rpc("ap_refresh_event", { p_event_id: inc.event_id }), "refresh");
      }
      must(await db.from("ap_location_suggestions")
        .update({ status: a.action === "accept" ? "accepted" : "rejected", reviewed_at: now }).eq("id", a.id).select("id"), "suggestion");
      return;
    }
    const d = must<any>(await db.from("ap_disputes").select("event_id").eq("id", a.id).single(), "dispute");
    if (d?.event_id && a.action !== "corrected") {
      must(await db.from("ap_events").update({ hidden: a.action === "remove", updated_at: now }).eq("id", d.event_id).select("id"), "event");
    }
    const status = a.action === "remove" ? "resolved_removed" : a.action === "restore" ? "resolved_kept" : "resolved_corrected";
    must(await db.from("ap_disputes").update({ status, resolved_at: now }).eq("id", a.id).select("id"), "dispute");
  },
};

// ── Demo: a few made-up queue items so the screen can be tried before the database is connected ──
const demo = {
  incidents: [
    { id: 9001, sourceName: "Daily territorial paper (sample)", sourceUrl: "https://www.loc.gov/collections/chronicling-america/",
      publishedDate: "1904-05-12", incidentDate: "1904-05-11", addressRaw: "Sample Hotel, Railroad Avenue", unit: null,
      city: "Albuquerque", county: "Bernalillo", placeKind: "boarding_house_or_hotel", cause: "accident",
      summary: "A fatal fall at a downtown hotel was reported.", confidence: 0.7, reviewReason: "boarding house or hotel", outsideArea: false,
      createdAt: "2026-10-21T12:00:00Z" },
    { id: 9002, sourceName: "Valley weekly (sample)", sourceUrl: "https://www.loc.gov/collections/chronicling-america/",
      publishedDate: "1931-08-02", incidentDate: "1931-08", addressRaw: "Sample Mercantile Co.", unit: null,
      city: "Belen", county: "Valencia", placeKind: "business", cause: "homicide",
      summary: "A fatal shooting at a store was reported.", confidence: 0.65, reviewReason: "business address", outsideArea: false,
      createdAt: "2026-10-21T12:05:00Z" },
  ] as ReviewIncident[],
  suggestions: [
    { id: 7001, incidentId: 9100, addressRaw: "312 S. Second St.", city: "Albuquerque", year: 1912,
      summary: "A house fire was reported to have claimed one life.", sourceUrl: "https://www.loc.gov/collections/chronicling-america/",
      suggestedLat: 35.0815, suggestedLng: -106.6505, suggestedAddress: "Near 3rd St SW & Gold Ave (sample)",
      rationale: "Sample suggestion: pre-renumbering addresses on Second Street ran differently; this is a demo row." },
  ] as ReviewSuggestion[],
  disputes: [
    { id: 5001, eventId: "00000000-0000-4000-8000-000000000026", eventYear: 2012, eventCity: "Albuquerque", eventCause: "homicide",
      eventHidden: true, requesterEmail: "family@example.com", relationship: "family", reason: "remove",
      details: "Sample request (demo data).", fastLane: true, createdAt: "2026-10-21T13:00:00Z" },
  ] as ReviewDispute[],
};

const demoStore: AdminStore = {
  async queue() {
    return {
      backend: "demo",
      incidents: demo.incidents,
      suggestions: demo.suggestions,
      disputes: demo.disputes,
      stats: { incidentsTotal: 41, eventsVisible: 41, harvestSpendUsd: 0, lastRun: null },
    };
  },
  async act(a) {
    if (a.type === "incident") demo.incidents = demo.incidents.filter((x) => x.id !== a.id);
    else if (a.type === "suggestion") demo.suggestions = demo.suggestions.filter((x) => x.id !== a.id);
    else demo.disputes = demo.disputes.filter((x) => x.id !== a.id);
  },
};

export function adminStore(): AdminStore {
  return hasSupabase() ? supabaseStore : demoStore;
}
