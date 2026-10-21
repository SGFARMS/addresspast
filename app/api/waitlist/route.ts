import { z } from "zod";
import { repo } from "@/lib/data";
import { clientIp, rateLimit, tooMany } from "@/lib/rate-limit";

const body = z.object({
  email: z.email().max(200),
  locale: z.enum(["en", "es"]).default("en"),
  county: z.string().max(40).nullable().optional(),
  website: z.string().max(0).optional(), // honeypot: must stay empty
});

export async function POST(req: Request) {
  const rl = await rateLimit("waitlist", clientIp(req));
  if (!rl.ok) return tooMany(rl.retryAfter);
  const parsed = body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: "bad_email" }, { status: 400 });
  try {
    const status = await repo().addToWaitlist({
      email: parsed.data.email.trim().toLowerCase(),
      locale: parsed.data.locale,
      county: parsed.data.county ?? null,
      referrer: req.headers.get("referer"),
    });
    return Response.json({ status });
  } catch (e) {
    console.error("[waitlist]", e);
    return Response.json({ error: "save_failed" }, { status: 500 });
  }
}
