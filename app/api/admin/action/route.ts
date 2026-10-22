import { z } from "zod";
import { isAdmin } from "@/lib/admin/auth";
import { adminStore } from "@/lib/admin/store";

const body = z.discriminatedUnion("type", [
  z.object({ type: z.literal("incident"), id: z.number().int(), action: z.enum(["approve", "hide"]) }),
  z.object({ type: z.literal("suggestion"), id: z.number().int(), action: z.enum(["accept", "reject"]) }),
  z.object({ type: z.literal("dispute"), id: z.number().int(), action: z.enum(["remove", "restore", "corrected"]) }),
]);

export async function POST(req: Request) {
  if (!(await isAdmin())) return Response.json({ error: "unauthorized" }, { status: 401 });
  const parsed = body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: "bad_request" }, { status: 400 });
  try {
    await adminStore().act(parsed.data);
    return Response.json({ ok: true });
  } catch (e) {
    console.error("[admin/action]", e);
    return Response.json({ error: "action_failed" }, { status: 500 });
  }
}
