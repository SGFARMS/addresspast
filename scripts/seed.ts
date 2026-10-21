/**
 * Load the ~40 FAKE seed records into Supabase (incidents + events).
 *   npm run seed            → insert (skips if already seeded)
 *   npm run seed -- --reset → delete previous seed rows first
 * Seed rows are tagged with source_url under example.org / loc.gov collection page
 * and event ids 00000000-0000-4000-8000-*, so they're easy to remove before launch.
 */
import { createClient } from "@supabase/supabase-js";
import { SEED_RECORDS, combineConfidence } from "../data/seed-records";

const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
if (!url || !key) {
  console.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (e.g. in .env.local) first.");
  process.exit(1);
}
const db = createClient(url, key, { auth: { persistSession: false } });

async function main() {
  const reset = process.argv.includes("--reset");
  const ids = SEED_RECORDS.map((r) => r.id);

  if (reset) {
    await db.from("ap_incidents").delete().in("event_id", ids);
    await db.from("ap_events").delete().in("id", ids);
    console.log("Removed previous seed rows.");
  } else {
    const { count } = await db.from("ap_events").select("id", { count: "exact", head: true }).in("id", ids);
    if (count) {
      console.log(`Already seeded (${count} events). Use --reset to reload.`);
      return;
    }
  }

  const events = SEED_RECORDS.map((r) => ({
    id: r.id,
    record_type: r.recordType,
    cause_category: r.cause,
    event_year: r.year,
    date_precision: r.datePrecision,
    city: r.city,
    county: r.county,
    geocode_precision: r.precision,
    geom: `SRID=4326;POINT(${r.lng} ${r.lat})`,
    summary: r.summary,
    summary_es: r.summaryEs,
    confidence: combineConfidence(r.sources.map((s) => s.confidence)),
    source_count: new Set(r.sources.map((s) => s.name)).size,
    verified: r.verified,
  }));
  const { error: e1 } = await db.from("ap_events").insert(events);
  if (e1) throw e1;

  const incidents = SEED_RECORDS.flatMap((r) =>
    r.sources.map((s, i) => ({
      source_url: `${s.url}#seed-${r.id.slice(-4)}-${i}`,
      source_name: s.name,
      published_date: s.published,
      incident_date: String(r.year),
      address_raw: `sample address ${r.id.slice(-4)}`,
      city: r.city,
      county: r.county,
      location_precision: r.precision === "street" || r.precision === "street_historic" ? "street_address" : r.precision === "city" ? "city_only" : r.precision,
      cause_category: r.cause,
      summary: r.summary,
      confidence: s.confidence,
      lat: r.lat,
      lng: r.lng,
      record_type: r.recordType,
      source_language: s.language ?? "en",
      geocode_status: "ok",
      geocode_source: "seed",
      geocode_precision: r.precision,
      verified: r.verified,
      event_id: r.id,
      summary_scrubbed: true,
    })),
  );
  const { error: e2 } = await db.from("ap_incidents").insert(incidents);
  if (e2) throw e2;

  // Coverage view feeds the free-check footnote
  await db.rpc("ap_refresh_area_coverage").then(
    () => undefined,
    () => console.warn("Run `refresh materialized view public.ap_area_coverage;` in the SQL editor to update coverage."),
  );
  await db.from("ap_pipeline_runs").insert({ job: "seed", trigger: "manual", status: "ok", finished_at: new Date().toISOString(), items_out: events.length });

  console.log(`Seeded ${events.length} events and ${incidents.length} source rows (all fake).`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
