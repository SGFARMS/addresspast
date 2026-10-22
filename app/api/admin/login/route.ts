import { z } from "zod";
import { adminCookie, checkPassword } from "@/lib/admin/auth";
import { clientIp, rateLimit, tooMany } from "@/lib/rate-limit";

const body = z.object({ password: z.string().min(1).max(200) });

export async function POST(req: Request) {
  const rl = await rateLimit("admin", clientIp(req));
  if (!rl.ok) return tooMany(rl.retryAfter);
  const parsed = body.safeParse(await req.json().catch(() => null));
  const token = parsed.success ? checkPassword(parsed.data.password) : null;
  if (!token) return Response.json({ error: "wrong_password" }, { status: 401 });
  return Response.json({ ok: true }, { headers: { "Set-Cookie": adminCookie(token) } });
}
