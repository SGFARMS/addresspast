"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { SlidersHorizontal, X } from "lucide-react";
import { siteConfig } from "@/site.config";
import { defaultFilters, filtersToQuery } from "@/lib/filters";
import { metersLabel } from "@/lib/format";
import { track } from "@/lib/analytics";
import type { AskResult, Bbox, CityBucket, FreeCheck, MapEvent, MapFilters, Place } from "@/lib/types";
import { Header, useTheme } from "@/components/ui/Header";
import { SearchBox } from "@/components/search/SearchBox";
import { TimelineSlider } from "@/components/map/TimelineSlider";
import { FilterPanel } from "@/components/map/FilterPanel";
import { Legend } from "@/components/map/Legend";
import { ResultsPanel } from "@/components/results/ResultsPanel";
import { Link } from "@/i18n/navigation";

const PropertyMap = dynamic(() => import("@/components/map/PropertyMap"), {
  ssr: false,
  loading: () => <div className="skeleton absolute inset-0 !rounded-none" aria-hidden />,
});

const MIN_YEAR = siteConfig.timeline.startYear;
const MAX_YEAR = new Date().getFullYear();

interface Chip {
  key: string;
  label: string;
  remove: () => void;
}

export function AppShell({ demo }: { demo: boolean }) {
  const t = useTranslations();
  const locale = useLocale();
  const { dark } = useTheme();

  const [filters, setFilters] = useState<MapFilters>(defaultFilters);
  const [years, setYears] = useState<[number, number]>([MIN_YEAR, MAX_YEAR]);
  const [bbox, setBbox] = useState<Bbox | null>(null);
  const [events, setEvents] = useState<MapEvent[]>([]);
  const [cities, setCities] = useState<CityBucket[]>([]);
  const [place, setPlace] = useState<Place | null>(null);
  const [check, setCheck] = useState<FreeCheck | null>(null);
  const [checkLoading, setCheckLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [flyTo, setFlyTo] = useState<{ lat: number; lng: number; zoom?: number; key: number } | null>(null);
  const [asked, setAsked] = useState<AskResult | null>(null);
  const [asking, setAsking] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [sheetTall, setSheetTall] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const checkReq = useRef(0);

  // ── map data (all years; the timeline filters client-side) ───────────
  useEffect(() => {
    if (!bbox) return;
    const ctrl = new AbortController();
    const timer = setTimeout(async () => {
      const qs = new URLSearchParams({ bbox: bbox.map((n) => n.toFixed(4)).join(","), ...filtersToQuery(filters) });
      try {
        const res = await fetch(`/api/map?${qs}`, { signal: ctrl.signal });
        if (res.status === 429) return setNotice(t("errors.rateLimited"));
        const json = await res.json();
        setEvents(json.events ?? []);
        setCities(json.cities ?? []);
      } catch {
        /* aborted */
      }
    }, 220);
    return () => { clearTimeout(timer); ctrl.abort(); };
  }, [bbox, filters, t]);

  // ── free check ──────────────────────────────────────────
  const runCheck = useCallback(
    async (p: Place, opts: { fly?: boolean } = {}) => {
      const req = ++checkReq.current;
      setPlace(p);
      setSelectedId(null);
      setCheck(null);
      setError(null);
      setCheckLoading(true);
      if (opts.fly !== false) setFlyTo({ lat: p.lat, lng: p.lng, zoom: 16.2, key: Date.now() });
      try {
        const res = await fetch("/api/check", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lat: p.lat, lng: p.lng, city: p.city, types: filters.recordTypes }),
        });
        const json = await res.json();
        if (req !== checkReq.current) return;
        if (res.status === 429) setError(t("errors.rateLimited"));
        else if (res.status === 422) setError(t("search.outsideNm"));
        else if (!res.ok) setError(t("errors.generic"));
        else setCheck(json);
      } catch {
        if (req === checkReq.current) setError(t("errors.generic"));
      } finally {
        if (req === checkReq.current) setCheckLoading(false);
      }
    },
    [filters.recordTypes, t],
  );

  // Re-run the check if the record types change while a place is open
  const typesKey = filters.recordTypes.join(",");
  const placeRef = useRef(place);
  placeRef.current = place;
  useEffect(() => {
    if (placeRef.current) void runCheck(placeRef.current, { fly: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [typesKey]);

  const pick = useCallback(
    async (lat: number, lng: number) => {
      const fallback: Place = { label: `${lat.toFixed(5)}, ${lng.toFixed(5)}`, lat, lng, city: null, county: null, kind: "place" };
      void runCheck(fallback, { fly: false });
      try {
        const res = await fetch(`/api/places/reverse?lat=${lat}&lng=${lng}`);
        if (res.status === 422) { setError(t("search.outsideNm")); setCheckLoading(false); return; }
        const json = await res.json();
        if (json.place) {
          setPlace((cur) => (cur && cur.lat === lat && cur.lng === lng ? { ...json.place, lat, lng } : cur));
          if (json.place.city) void runCheck({ ...json.place, lat, lng }, { fly: false });
        }
      } catch {
        /* keep coordinates label */
      }
    },
    [runCheck, t],
  );

  const locate = () => {
    if (!navigator.geolocation) return setNotice(t("search.locateDenied"));
    setNotice(t("search.locating"));
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setNotice(null);
        setFlyTo({ lat: pos.coords.latitude, lng: pos.coords.longitude, zoom: 16.2, key: Date.now() });
        void pick(pos.coords.latitude, pos.coords.longitude);
      },
      () => setNotice(t("search.locateDenied")),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

  const askQuestion = async (q: string) => {
    setAsking(true);
    setNotice(null);
    try {
      const res = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ q }) });
      if (res.status === 429) return setNotice(t("errors.rateLimited"));
      if (!res.ok) return setNotice(t("errors.generic"));
      const a = (await res.json()) as AskResult;
      setAsked(a);
      setFilters((f) => ({
        ...f,
        recordTypes: a.recordTypes?.length ? a.recordTypes : f.recordTypes,
        causes: a.causes?.length ? a.causes : null,
        includeNatural: a.includeNatural ?? (a.causes?.includes("natural") ? true : f.includeNatural),
      }));
      setYears([a.yearFrom ?? MIN_YEAR, a.yearTo ?? MAX_YEAR]);
      if (a.place) {
        const zoom = a.place.kind === "area" ? 12.5 : (a.radiusM ?? 500) > 800 ? 14 : 15.5;
        setFlyTo({ lat: a.place.lat, lng: a.place.lng, zoom, key: Date.now() });
        if (a.place.kind !== "area") void runCheck(a.place, { fly: false });
      } else if (!a.recordTypes && !a.causes && a.yearFrom == null && a.yearTo == null) {
        setNotice(t("search.noResults"));
      }
    } finally {
      setAsking(false);
    }
  };

  // ── chips: what Claude (or the rules) read from the question ────────
  const chips: Chip[] = useMemo(() => {
    if (!asked) return [];
    const c: Chip[] = [];
    const l = (k: string, v?: Record<string, string | number>) => t(`filters.${k}`, v);
    if (asked.place) c.push({ key: "place", label: l("chipPlace", { place: asked.place.label.split(",")[0] }), remove: () => setAsked({ ...asked, place: null }) });
    if (asked.radiusM && asked.place) c.push({ key: "radius", label: l("chipRadius", { distance: metersLabel(asked.radiusM, locale) }), remove: () => setAsked({ ...asked, radiusM: null }) });
    for (const rt of asked.recordTypes ?? [])
      c.push({ key: `rt-${rt}`, label: t(`types.${rt}`), remove: () => { setFilters((f) => ({ ...f, recordTypes: f.recordTypes.length > 1 ? f.recordTypes.filter((x) => x !== rt) : ["death"] })); setAsked({ ...asked, recordTypes: asked.recordTypes!.filter((x) => x !== rt) }); } });
    for (const cause of asked.causes ?? [])
      c.push({ key: `c-${cause}`, label: t(`causes.${cause}`), remove: () => { setFilters((f) => ({ ...f, causes: f.causes && f.causes.length > 1 ? f.causes.filter((x) => x !== cause) : null })); setAsked({ ...asked, causes: asked.causes!.filter((x) => x !== cause) }); } });
    if (asked.yearFrom != null || asked.yearTo != null) {
      const label = asked.yearFrom != null && asked.yearTo != null ? l("chipYears", { from: asked.yearFrom, to: asked.yearTo }) : asked.yearTo != null ? l("chipBefore", { year: asked.yearTo + 1 }) : l("chipAfter", { year: asked.yearFrom! });
      c.push({ key: "years", label, remove: () => { setYears([MIN_YEAR, MAX_YEAR]); setAsked({ ...asked, yearFrom: null, yearTo: null }); } });
    }
    return c;
  }, [asked, t, locale]);

  const closeResults = () => { setPlace(null); setCheck(null); setSelectedId(null); setError(null); };
  const mapLabels = useMemo(
    () => ({
      region: t("home.headline"),
      approx: t("legend.approx"),
      cityBadge: (city: string, n: number) => `${city}: ${t("area.total", { count: n })} · ${t("legend.city")}`,
      cluster: (n: number) => t("area.total", { count: n }),
    }),
    [t],
  );

  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <Header compact />
      <main className="relative flex-1 overflow-hidden">
        <PropertyMap
          events={events}
          cities={cities}
          years={years}
          dark={dark}
          searched={place}
          radiusM={siteConfig.check.nearbyRadiusM}
          selectedId={selectedId}
          flyTo={flyTo}
          labels={mapLabels}
          onBounds={setBbox}
          onSelect={(id) => {
            setSelectedId(id);
            track("record_open", { from: "map" });
            if (!place) {
              const e = events.find((x) => x.id === id);
              if (e) void runCheck({ label: t("check.atThisAddress"), lat: e.lat, lng: e.lng, city: null, county: null, kind: "place" }, { fly: false }).then(() => setSelectedId(id));
            }
          }}
          onPick={(lat, lng) => void pick(lat, lng)}
          onCity={(_city, lat, lng) => setFlyTo({ lat, lng, zoom: 13, key: Date.now() })}
        />

        {/* Search column: floats on top (phone), left column (desktop) */}
        <div className="pointer-events-none absolute inset-x-0 top-0 z-20 flex flex-col gap-3 p-3 md:bottom-0 md:right-auto md:w-[420px] md:p-4">
          <div className="pointer-events-auto rounded-2xl border border-line bg-surface p-3 shadow-card md:p-4">
            {!place && (
              <div className="mb-3 px-1">
                <h1 className="font-serif text-2xl font-semibold tracking-tight md:text-[1.75rem]">{t("home.headline")}</h1>
                <p className="mt-1 hidden text-sm text-ink-2 sm:block">{t("home.sub")}</p>
              </div>
            )}
            <SearchBox onPlace={(p) => { setAsked(null); void runCheck(p); }} onAsk={askQuestion} onLocate={locate} busy={asking} />
            {chips.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-1.5" aria-label={t("filters.fromQuestion")}>
                {chips.map((c) => (
                  <button key={c.key} type="button" onClick={c.remove} aria-label={t("filters.removeChip", { label: c.label })} className="inline-flex items-center gap-1 rounded-full border border-accent/40 bg-accent-soft px-2.5 py-1 text-xs font-medium">
                    {c.label} <X size={12} aria-hidden />
                  </button>
                ))}
              </div>
            )}
            {notice && <p className="mt-2 px-1 text-xs text-ink-2" role="status">{notice}</p>}
            {!place && (
              <div className="mt-3 hidden space-y-1.5 px-1 text-xs text-ink-3 md:block">
                <p>{t("search.examples")}</p>
                <p>{t("search.tapHint")}</p>
                <p className="font-medium text-ink-2">{t("home.trust")}</p>
              </div>
            )}
            {demo && !place && (
              <p className="mt-3 rounded-lg bg-adobe-soft px-3 py-2 text-xs text-ink">{t("home.demoData")}</p>
            )}
          </div>

          {/* Results: bottom sheet on phones, column panel on desktop */}
          {place && (
            <div
              className={`pointer-events-auto fixed inset-x-0 bottom-0 z-30 overflow-y-auto rounded-t-3xl border border-line bg-surface p-4 pb-[max(1rem,env(safe-area-inset-bottom))] shadow-card md:static md:z-auto md:max-h-none md:flex-1 md:rounded-2xl ${sheetTall ? "max-h-[85dvh]" : "max-h-[46dvh]"}`}
            >
              <button
                type="button"
                onClick={() => setSheetTall((s) => !s)}
                aria-label={sheetTall ? "Collapse" : "Expand"}
                aria-expanded={sheetTall}
                className="mx-auto -mt-1 mb-2 block h-1.5 w-12 rounded-full bg-line md:hidden"
              />
              <ResultsPanel
                place={place}
                check={check}
                loading={checkLoading}
                error={error}
                includeNatural={filters.includeNatural}
                onlyDeaths={filters.recordTypes.length === 1 && filters.recordTypes[0] === "death"}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onToggleNatural={(on) => setFilters((f) => ({ ...f, includeNatural: on, causes: f.causes && on ? [...f.causes, "natural"] : f.causes }))}
                onClose={closeResults}
              />
            </div>
          )}
        </div>

        {/* Map tools: legend, filters, timeline */}
        <div className={`pointer-events-none absolute bottom-[154px] right-3 z-10 flex flex-col items-end gap-2 md:bottom-4 md:right-4 ${place ? "max-md:hidden" : ""}`}>
          <Legend filters={filters} />
        </div>
        <div className={`pointer-events-none absolute inset-x-3 bottom-3 z-10 flex flex-col gap-2 md:bottom-4 md:left-[452px] md:right-40 ${place ? "max-md:hidden" : ""}`}>
          <div className="pointer-events-auto flex gap-2">
            <button type="button" onClick={() => setFilterOpen(true)} className="flex items-center gap-1.5 rounded-xl border border-line bg-surface px-3 py-2 text-xs font-medium shadow-card hover:border-accent">
              <SlidersHorizontal size={14} aria-hidden /> {t("filters.open")}
              {!filters.includeNatural && <span className="sr-only">({t("filters.naturalNote")})</span>}
            </button>
            <Link href="/nm" className="rounded-xl border border-line bg-surface px-3 py-2 text-xs font-medium shadow-card hover:border-accent md:hidden">
              {t("nav.areas")}
            </Link>
          </div>
          <div className="pointer-events-auto max-w-2xl">
            <TimelineSlider events={events} cities={cities} min={MIN_YEAR} max={MAX_YEAR} value={years} onChange={setYears} />
          </div>
        </div>

        <FilterPanel
          open={filterOpen}
          value={filters}
          onChange={(f) => { setFilters(f); track("filter_change"); }}
          onClose={() => setFilterOpen(false)}
        />
      </main>
    </div>
  );
}
