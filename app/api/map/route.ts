import { repo } from "@/lib/data";
import { filtersFromQuery, mapQuerySchema } from "@/lib/filters";
import { clampBbox } from "@/lib/geo";
import { clientIp, rateLimit, tooMany } from "@/lib/rate-limit";
import { siteConfig } from "@/site.config";
import type { Bbox } from "@/lib/types";

/**
 * Map data for a bounding box. Returns every year so the timeline slider and
 * decade histogram filter instantly on the client without refetching.
 */
export async function GET(req: Request) {
  const rl = await rateLimit("map", clientIp(req));
  if (!rl.ok) return tooMany(rl.retryAfter);
  const parsed = mapQuerySchema.safeParse(Object.fromEntries(new URL(req.url).searchParams));
  if (!parsed.success) return Response.json({ error: "bad_request" }, { status: 400 });
  const bbox = clampBbox(parsed.data.bbox as Bbox, siteConfig.bounds);
  const f = filtersFromQuery(parsed.data);
  try {
    const [events, cities] = await Promise.all([repo().mapEvents(bbox, f), repo().cityDecades(f)]);
    return Response.json(
      { events, cities },
      { headers: { "Cache-Control": "public, s-maxage=300, stale-while-revalidate=3600" } },
    );
  } catch (e) {
    console.error("[map]", e);
    return Response.json({ error: "map_failed" }, { status: 500 });
  }
}
