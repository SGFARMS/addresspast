import { z } from "zod";
import { repo } from "@/lib/data";
import { clientIp, rateLimit, tooMany } from "@/lib/rate-limit";

/**
 * Report an error or request removal. Requests from family, owners and tenants about records
 * from the last 10 years take the fast lane: the record is hidden right away, then reviewed.
 */
const body = z.object({
  eventId: z.uuid(),
  email: z.email().max(200),
  relationship: z.enum(["owner", "family", "tenant", "agent", "other"]),
  reason: z.enum(["remove", "wrong_location", "wrong_details", "other"]),
  details: z.string().max(2000).optional(),
  website: z.string().max(0).optional(), // honeypot: must stay empty
});

export async function POST(req: Request) {
  const rl = await rateLimit("removal", clientIp(req));
  if (!rl.ok) return tooMany(rl.retryAfter);
  const parsed = body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: "bad_request" }, { status: 400 });
  const d = parsed.data;
  try {
    const r = await repo().requestRemoval({
      eventId: d.eventId,
      email: d.email.trim().toLowerCase(),
      relationship: d.relationship,
      reason: d.reason,
      details: d.details?.trim() || null,
    });
    if (!r.ok) return Response.json({ error: "not_found" }, { status: 404 });
    return Response.json({ status: "received", fastLane: r.fastLane });
  } catch (e) {
    console.error("[removal]", e);
    return Response.json({ error: "save_failed" }, { status: 500 });
  }
}
