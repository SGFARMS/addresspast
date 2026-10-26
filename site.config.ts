/**
 * AddressPast — every site-specific setting lives here.
 * Swap this file to reuse the template for another lookup site.
 */

export const siteConfig = {
  // ── Brand ─────────────────────────────────────────────────────────────
  name: "AddressPast",
  logoText: "AddressPast",
  tagline: {
    en: "Know what happened here before you move in.",
    es: "Conozca lo que pasó aquí antes de mudarse.",
  },
  /** Change this one line when the custom domain is bought. */
  url: "https://history.skyhighwebsites.dev",
  contactEmail: "joerudys@ymail.com",

  // ── Launch state ──────────────────────────────────────────────────────
  /** false = waitlist home page, noindex everywhere, robots.txt disallow. */
  launched: true,
  /** Cookie set by /preview?key=PREVIEW_SECRET to bypass the waitlist. */
  previewCookie: "ap_preview",

  // ── Coverage ──────────────────────────────────────────────────────────
  state: { code: "NM", name: "New Mexico" },
  /** NM bounding box (west, south, east, north) used for geocoding + map. */
  bounds: [-109.06, 31.33, -103.0, 37.0] as [number, number, number, number],
  counties: [
    {
      slug: "bernalillo",
      name: "Bernalillo",
      cities: [{ slug: "albuquerque", name: "Albuquerque" }],
    },
    {
      slug: "sandoval",
      name: "Sandoval",
      cities: [{ slug: "rio-rancho", name: "Rio Rancho" }],
    },
    {
      slug: "valencia",
      name: "Valencia",
      cities: [
        { slug: "belen", name: "Belen" },
        { slug: "los-lunas", name: "Los Lunas" },
      ],
    },
  ],
  timeline: { startYear: 1860 },

  // ── Search + free check ───────────────────────────────────────────────
  check: {
    nearbyRadiusM: 250,
    approximateRadiusM: 150,
  },

  // ── Map ───────────────────────────────────────────────────────────────
  map: {
    /** Free OSM-based vector tiles. Swap for Mapbox/MapTiler later. */
    styleLight: "https://tiles.openfreemap.org/styles/positron",
    styleDark: "https://tiles.openfreemap.org/styles/dark",
    center: [-106.68, 34.85] as [number, number],
    zoom: 8.4,
  },

  /** Autocomplete provider. Nominatim's policy forbids autocomplete, so Photon is the default. */
  geocoder: {
    provider: "photon" as const,
    photonUrl: "https://photon.komoot.io",
    userAgent: "AddressPast/0.1 (history.skyhighwebsites.dev)",
  },

  // ── Feature flags ─────────────────────────────────────────────────────
  features: {
    /** Gate summaries + source links behind the paid report. Off during the pilot. */
    paywall: false,
    /** Natural-cause records hidden on the map until the user turns them on. */
    showNaturalByDefault: true,
    voiceSearch: true,
    askInPlainEnglish: true,
    areaSummaries: true,
    linkOutTools: [] as { label: string; url: string }[], // Phase 4: e.g. WaterMap NM
  },

  // ── AI (Anthropic) ────────────────────────────────────────────────────
  ai: {
    models: {
      fast: "claude-haiku-5-5", // triage, ask→filters, translation, scrub check
      smart: "claude-sonnet-5-5", // extraction, dedupe confirm, historic geo
    },
    /** USD per million tokens, for cost logging. Batch = 50% off. */
    pricing: {
      "claude-haiku-5-5": { input: 0.1, output: 0.5, cacheWrite: 0.125, cacheRead: 0.01 },
      "claude-sonnet-5-5": { input: 2, output: 10, cacheWrite: 2.5, cacheRead: 0.1 },
    } as Record<string, { input: number; output: number; cacheWrite: number; cacheRead: number }>,
    features: {
      ask: true,
      areaSummary: true,
    },
  },

  // ── Pricing (Phase 3) ────────────────────────────────────────────────
  pricing: {
    reportUsd: 7,
    proMonthlyUsd: 29,
  },

  // ── Rate limits (per IP) ─────────────────────────────────────────────
  rateLimit: {
    check: { requests: 30, window: "1 m" },
    map: { requests: 120, window: "1 m" },
    suggest: { requests: 90, window: "1 m" },
    ask: { requests: 10, window: "1 m" },
    waitlist: { requests: 5, window: "10 m" },
    removal: { requests: 5, window: "1 h" },
    admin: { requests: 10, window: "10 m" },
  },

  // ── Theme tokens (see app/globals.css) ───────────────────────────────
  theme: {
    accent: "#4F6F5E", // sage
    adobe: "#B7724F",
  },

  /** Marker colors by cause: muted, legend-driven, never blood red. */
  causeColors: {
    accident: "#5E7A8F",
    homicide: "#6E5C80",
    suicide: "#857A70",
    fire: "#B08A47",
    natural: "#8E9C84",
    unknown: "#9A928A",
  } as Record<string, string>,
} as const;

export type SiteConfig = typeof siteConfig;
export type Locale = "en" | "es";
