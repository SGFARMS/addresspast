import { reversePlace } from "@/lib/places";
import { isInNM } from "@/lib/geo";
import { clientIp, rateLimit, tooMany } from "@/lib/rate-limit";

export async function GET(req: Request) {
  const sp = new URL(req.url).searchParams;
  const lat = Number(sp.get("lat"));
  const lng = Number(sp.get("lng"));
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return Response.json({ error: "bad_point" }, { status: 400 });
  if (!isInNM(lat, lng)) return Response.json({ error: "outside_nm" }, { status: 422 });
  const rl = await rateLimit("suggest", clientIp(req));
  if (!rl.ok) return tooMany(rl.retryAfter);
  try {
    const place = await reversePlace(lat, lng);
    return Response.json({ place });
  } catch {
    return Response.json({ place: null });
  }
}
