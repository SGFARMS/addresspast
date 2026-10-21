import type { DatePrecision, GeoPrecision } from "./types";

export function yearLabel(year: number | null, precision: DatePrecision | null) {
  if (year == null) return null;
  if (precision === "decade") return `${Math.floor(year / 10) * 10}s`;
  return String(year);
}

export function confidenceBand(c: number): "high" | "medium" | "low" {
  if (c >= 0.75) return "high";
  if (c >= 0.5) return "medium";
  return "low";
}

export function isApproximate(p: GeoPrecision) {
  return p === "street_historic" || p === "intersection" || p === "landmark";
}

export function metersLabel(m: number, locale: string) {
  if (m < 1000) return `${Math.round(m / 5) * 5} m`;
  return `${(m / 1000).toLocaleString(locale, { maximumFractionDigits: 1 })} km`;
}

export function dateLabel(iso: string | null, locale: string) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(locale === "es" ? "es-US" : "en-US", { year: "numeric", month: "short", day: "numeric" });
}

export function cn(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}
