import { siteConfig } from "@/site.config";

export function findCounty(slug: string) {
  return siteConfig.counties.find((c) => c.slug === slug) ?? null;
}

export function findCity(countySlug: string, citySlug: string) {
  const county = findCounty(countySlug);
  const city = county?.cities.find((c) => c.slug === citySlug) ?? null;
  return county && city ? { county, city } : null;
}

/** Rough view boxes for area maps (w, s, e, n). */
export const AREA_VIEW: Record<string, { center: [number, number]; zoom: number }> = {
  bernalillo: { center: [-106.63, 35.08], zoom: 10.2 },
  valencia: { center: [-106.76, 34.73], zoom: 10 },
  sandoval: { center: [-106.67, 35.25], zoom: 10.5 },
  albuquerque: { center: [-106.64, 35.09], zoom: 11.6 },
  belen: { center: [-106.775, 34.662], zoom: 13.4 },
  "los-lunas": { center: [-106.733, 34.806], zoom: 13.2 },
  "rio-rancho": { center: [-106.664, 35.233], zoom: 12.8 },
};
