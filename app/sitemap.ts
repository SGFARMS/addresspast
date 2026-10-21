import type { MetadataRoute } from "next";
import { siteConfig } from "@/site.config";

/** Home + aggregate area pages only. Never per-address pages. */
export default function sitemap(): MetadataRoute.Sitemap {
  if (!siteConfig.launched) return [];
  const base = siteConfig.url;
  const paths = ["", "/nm"];
  for (const c of siteConfig.counties) {
    paths.push(`/nm/${c.slug}`);
    for (const city of c.cities) paths.push(`/nm/${c.slug}/${city.slug}`);
  }
  return paths.map((p) => ({
    url: `${base}${p || "/"}`,
    changeFrequency: "weekly",
    alternates: { languages: { en: `${base}${p || "/"}`, es: `${base}/es${p}` } },
  }));
}
