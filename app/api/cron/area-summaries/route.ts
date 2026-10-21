import { repo } from "@/lib/data";
import { getAreaSummary } from "@/lib/ai/area-summary";
import { siteConfig } from "@/site.config";

export const maxDuration = 300;

/** Weekly (vercel.json): regenerate AI area summaries whose stats changed. */
export async function GET(req: Request) {
  if (process.env.CRON_SECRET && req.headers.get("authorization") !== `Bearer ${process.env.CRON_SECRET}`) {
    return new Response("unauthorized", { status: 401 });
  }
  const done: string[] = [];
  for (const county of siteConfig.counties) {
    const areas = [{ city: null as string | null, name: `${county.name} County` }, ...county.cities.map((c) => ({ city: c.name, name: c.name }))];
    for (const a of areas) {
      const stats = await repo().areaStats(county.name, a.city, false);
      for (const locale of ["en", "es"]) {
        await getAreaSummary({ county: county.name, city: a.city, area: a.name, stats, locale, generate: true });
        done.push(`${a.name}/${locale}`);
      }
    }
  }
  return Response.json({ ok: true, done });
}
