import { adminCookie } from "@/lib/admin/auth";

export async function POST() {
  return Response.json({ ok: true }, { headers: { "Set-Cookie": adminCookie("", 0) } });
}
