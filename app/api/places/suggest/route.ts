import { suggestPlaces } from "@/lib/places";
import { clientIp, rateLimit, tooMany } from "@/lib/rate-limit";

export async function GET(req: Request) {
  const q = new URL(req.url).searchParams.get("q")?.trim() ?? "";
  if (q.length < 3) return Response.json({ places: [] });
  const rl = await rateLimit("suggest", clientIp(req));
  if (!rl.ok) return tooMany(rl.retryAfter);
  try {
    const places = await suggestPlaces(q.slice(0, 120));
    return Response.json({ places }, { headers: { "Cache-Control": "public, s-maxage=86400, stale-while-revalidate=604800" } });
  } catch (e) {
    console.error("[suggest]", e);
    return Response.json({ places: [], error: "geocoder_unavailable" }, { status: 502 });
  }
}
