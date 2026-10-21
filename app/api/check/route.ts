import { z } from "zod";
import { repo } from "@/lib/data";
import { isInNM } from "@/lib/geo";
import { clientIp, rateLimit, tooMany } from "@/lib/rate-limit";
import { siteConfig } from "@/site.config";
import { RECORD_TYPES } from "@/lib/types";

const body = z.object({
  lat: z.number(),
  lng: z.number(),
  city: z.string().max(80).nullable().optional(),
  types: z.array(z.enum(RECORD_TYPES as [string, ...string[]])).optional(),
});

/** The free check: counts + year/category/precision only. Summaries and links come from /api/events/[id]. */
export async function POST(req: Request) {
  const rl = await rateLimit("check", clientIp(req));
  if (!rl.ok) return tooMany(rl.retryAfter);
  const parsed = body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: "bad_request" }, { status: 400 });
  const { lat, lng, city, types } = parsed.data;
  if (!isInNM(lat, lng)) return Response.json({ error: "outside_nm" }, { status: 422 });
  try {
    const result = await repo().freeCheck({
      lat,
      lng,
      city: city ?? null,
      nearM: siteConfig.check.nearbyRadiusM,
      recordTypes: types?.length ? types : ["death"],
    });
    return Response.json(result, { headers: { "Cache-Control": "private, no-store" } });
  } catch (e) {
    console.error("[check]", e);
    return Response.json({ error: "check_failed" }, { status: 500 });
  }
}
