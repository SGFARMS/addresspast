import { z } from "zod";
import { ask } from "@/lib/ai/ask";
import { clientIp, rateLimit, tooMany } from "@/lib/rate-limit";
import { siteConfig } from "@/site.config";

const body = z.object({ q: z.string().min(3).max(400) });

export async function POST(req: Request) {
  if (!siteConfig.features.askInPlainEnglish) return Response.json({ error: "disabled" }, { status: 404 });
  const rl = await rateLimit("ask", clientIp(req));
  if (!rl.ok) return tooMany(rl.retryAfter);
  const parsed = body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: "bad_request" }, { status: 400 });
  try {
    return Response.json(await ask(parsed.data.q));
  } catch (e) {
    console.error("[ask]", e);
    return Response.json({ error: "ask_failed" }, { status: 500 });
  }
}
