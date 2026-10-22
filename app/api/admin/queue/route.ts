import { isAdmin } from "@/lib/admin/auth";
import { adminStore } from "@/lib/admin/store";

export async function GET() {
  if (!(await isAdmin())) return Response.json({ error: "unauthorized" }, { status: 401 });
  try {
    return Response.json(await adminStore().queue(), { headers: { "Cache-Control": "private, no-store" } });
  } catch (e) {
    console.error("[admin/queue]", e);
    return Response.json({ error: "queue_failed" }, { status: 500 });
  }
}
