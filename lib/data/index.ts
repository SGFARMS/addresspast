import "server-only";
import { hasSupabase } from "@/lib/supabase/server";
import { demoRepo } from "./demo";
import { supabaseRepo } from "./supabase";
import type { Repo } from "./repo";
import type { AreaStats } from "@/lib/types";
import { siteConfig } from "@/site.config";

/** Supabase when configured, otherwise the in-memory demo dataset (fake seed records). */
export function repo(): Repo {
  return hasSupabase() ? supabaseRepo : demoRepo;
}

/**
 * Area stats for the county/city pages. Those pages are prerendered at build time, so a database
 * hiccup during a deploy used to fail the whole build. During the build we fall back to empty stats
 * (the page refreshes from the database within its revalidate window); at runtime errors still
 * throw, so ISR keeps serving the last good page instead of caching an empty one.
 */
export async function areaStatsForPage(county: string, city: string | null): Promise<AreaStats> {
  try {
    return await repo().areaStats(county, city, siteConfig.features.showNaturalByDefault);
  } catch (e) {
    if (process.env.NEXT_PHASE !== "phase-production-build") throw e;
    console.warn(`[build] area stats for ${city ?? county} unavailable, prerendering empty: ${(e as Error).message}`);
    return { total: 0, byDecade: {}, byCause: {}, byPrecision: {}, verified: 0, coverage: null };
  }
}

export type { Repo } from "./repo";
