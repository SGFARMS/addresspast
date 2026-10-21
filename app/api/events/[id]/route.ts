import { repo } from "@/lib/data";
import { scrubNames } from "@/lib/scrub/names";
import { clientIp, rateLimit, tooMany } from "@/lib/rate-limit";
import { siteConfig } from "@/site.config";

/** One record card. Summary + source links are gated by features.paywall. */
export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const rl = await rateLimit("map", clientIp(req));
  if (!rl.ok) return tooMany(rl.retryAfter);
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/i.test(id)) return Response.json({ error: "bad_id" }, { status: 400 });
  const locale = new URL(req.url).searchParams.get("locale") === "es" ? "es" : "en";
  const full = !siteConfig.features.paywall;
  try {
    const detail = await repo().eventDetail(id, full, locale);
    if (!detail) return Response.json({ error: "not_found" }, { status: 404 });
    if (detail.summary) {
      const { text, hits } = scrubNames(detail.summary);
      detail.summary = text;
      if (hits.length) {
        await repo()
          .logScrubHits(hits.map((h) => ({ eventId: id, field: "summary", matchedText: h, detector: "regex", context: "response" })))
          .catch(() => undefined);
      }
    }
    return Response.json(detail, { headers: { "Cache-Control": "public, s-maxage=600" } });
  } catch (e) {
    console.error("[event]", e);
    return Response.json({ error: "event_failed" }, { status: 500 });
  }
}
