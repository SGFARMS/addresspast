import "server-only";
import { siteConfig } from "@/site.config";
import { isInNM } from "@/lib/geo";
import type { Place } from "@/lib/types";

/**
 * Geocoder adapter. Photon (OSM-based, allows search-as-you-type) by default.
 * Nominatim's public API forbids autocomplete, so it is not used here.
 * Results are cached by Next's data cache for a day.
 */

interface PhotonFeature {
  geometry: { coordinates: [number, number] };
  properties: {
    name?: string;
    housenumber?: string;
    street?: string;
    city?: string;
    town?: string;
    village?: string;
    district?: string;
    county?: string;
    state?: string;
    postcode?: string;
    type?: string;
    osm_value?: string;
  };
}

const headers = { "User-Agent": siteConfig.geocoder.userAgent, Accept: "application/json" };

function toPlace(f: PhotonFeature): Place | null {
  const p = f.properties;
  const [lng, lat] = f.geometry.coordinates;
  if (p.state && p.state !== "New Mexico") return null;
  if (!isInNM(lat, lng)) return null;
  const city = p.city ?? p.town ?? p.village ?? null;
  const line1 = p.housenumber && p.street ? `${p.housenumber} ${p.street}` : p.street ?? p.name ?? "";
  const label = [p.name && p.name !== p.street && !p.housenumber ? p.name : null, line1 !== p.name ? line1 : null, city]
    .filter(Boolean)
    .join(", ") || (p.name ?? "");
  const kind: Place["kind"] = p.housenumber ? "address" : p.type === "street" ? "street" : p.type === "city" || p.type === "county" || p.type === "district" ? "area" : "place";
  return {
    label: label || `${lat.toFixed(5)}, ${lng.toFixed(5)}`,
    lat,
    lng,
    city,
    county: p.county?.replace(/ County$/, "") ?? null,
    kind,
  };
}

export async function suggestPlaces(q: string, limit = 6): Promise<Place[]> {
  const [w, s, e, n] = siteConfig.bounds;
  const url = new URL("/api/", siteConfig.geocoder.photonUrl);
  url.searchParams.set("q", q);
  url.searchParams.set("limit", String(limit * 2));
  url.searchParams.set("lang", "en");
  url.searchParams.set("bbox", `${w},${s},${e},${n}`);
  url.searchParams.set("lat", String(siteConfig.map.center[1]));
  url.searchParams.set("lon", String(siteConfig.map.center[0]));
  const res = await fetch(url, { headers, next: { revalidate: 86400 } });
  if (!res.ok) throw new Error(`geocoder ${res.status}`);
  const json = (await res.json()) as { features: PhotonFeature[] };
  const seen = new Set<string>();
  return json.features
    .map(toPlace)
    .filter((p): p is Place => {
      if (!p) return false;
      const key = p.label.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, limit);
}

export async function reversePlace(lat: number, lng: number): Promise<Place | null> {
  const url = new URL("/reverse", siteConfig.geocoder.photonUrl);
  url.searchParams.set("lat", lat.toFixed(6));
  url.searchParams.set("lon", lng.toFixed(6));
  url.searchParams.set("lang", "en");
  url.searchParams.set("limit", "1");
  const res = await fetch(url, { headers, next: { revalidate: 86400 } });
  if (!res.ok) return null;
  const json = (await res.json()) as { features: PhotonFeature[] };
  const p = json.features[0] ? toPlace(json.features[0]) : null;
  // Keep the exact tapped point; the label is only a description of the area.
  return p ? { ...p, lat, lng } : null;
}
