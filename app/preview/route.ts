import { siteConfig } from "@/site.config";

/** Secret preview link: /preview?key=PREVIEW_SECRET bypasses the waitlist. /preview?off clears it. */
export async function GET(req: Request) {
  const url = new URL(req.url);
  const res = (cookie: string) =>
    new Response(null, { status: 303, headers: { Location: "/", "Set-Cookie": cookie } });
  if (url.searchParams.has("off")) {
    return res(`${siteConfig.previewCookie}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax; Secure`);
  }
  const secret = process.env.PREVIEW_SECRET;
  if (!secret || url.searchParams.get("key") !== secret) return new Response("Not found", { status: 404 });
  return res(`${siteConfig.previewCookie}=1; Path=/; Max-Age=${60 * 60 * 24 * 30}; HttpOnly; SameSite=Lax; Secure`);
}
