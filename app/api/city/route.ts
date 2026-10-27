import { z } from "zod";
import { repo } from "@/lib/data";
import { withPreviews } from "@/lib/data/previews";
import { filtersFromQuery, mapQuerySchema } from "@/lib/filters";
import { clientIp, rateLimit, tooMany } from "@/lib/rate-limit";

/**
 * Records placed only at town level ("Gallup, 1912"). The map shows these as a town badge with a
 * count; this lists them so a tap on the badge (or on a spot in that town) shows the actual records.
 */
const schema = mapQuerySchema.omit({ bbox: true }).extend({ city: z.string().trim().min(2).max(80) });

export async function GET(req: Request) {
  const rl = await rateLimit("map", clientIp(req));
  if (!rl.ok) return tooMany(rl.retryAfter);
  const parsed = schema.safeParse(Object.fromEntries(new URL(req.url).searchParams));
  if (!parsed.success) return Response.json({ error: "bad_request" }, { status: 400 });
  // filtersFromQuery only reads the filter fields, so the missing bbox is fine
  const f = filtersFromQuery({ ...parsed.data, bbox: [0, 0, 0, 0] });
  try {
    const locale = new URL(req.url).searchParams.get("locale") === "es" ? "es" : "en";
    const items = await withPreviews(await repo().cityEvents(parsed.data.city, f), locale);
    return Response.json({ city: parsed.data.city, items }, { headers: { "Cache-Control": "public, s-maxage=300, stale-while-revalidate=3600" } });
  } catch (e) {
    console.error("[city]", e);
    return Response.json({ error: "city_failed" }, { status: 500 });
  }
}
