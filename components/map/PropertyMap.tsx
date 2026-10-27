"use client";

import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
type GeoJSONSource = maplibregl.GeoJSONSource;
type MLMap = maplibregl.Map;

// MapLibre v6 is ESM-only; bundlers need the worker URL set once (Turbopack/Next pattern from the MapLibre docs).
maplibregl.setWorkerUrl(new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).toString());
import "maplibre-gl/dist/maplibre-gl.css";
import { siteConfig } from "@/site.config";
import { circleRing } from "@/lib/geo";
import { isApproximate } from "@/lib/format";
import { CAUSES, RECORD_TYPES, type Bbox, type CityBucket, type MapEvent, type RecordType } from "@/lib/types";
import { TYPE_SHAPES, markerColor } from "@/components/records/bits";

export interface MapLabels {
  region: string;
  approx: string;
  cityBadge: (city: string, n: number) => string;
  cluster: (n: number) => string;
}

interface Props {
  events: MapEvent[];
  cities: CityBucket[];
  years: [number, number];
  dark: boolean;
  searched: { lat: number; lng: number } | null;
  radiusM: number;
  selectedId: string | null;
  flyTo: { lat: number; lng: number; zoom?: number; key: number } | null;
  labels: MapLabels;
  onBounds: (b: Bbox) => void;
  onSelect: (id: string) => void;
  onPick: (lat: number, lng: number) => void;
  onCity: (city: string, lat: number, lng: number) => void;
}

type Shape = "circle" | "triangle" | "diamond" | "square" | "hexagon";

/** Draw a marker icon on a canvas so each record type gets its own shape. */
function makeIcon(shape: Shape, color: string, hollow: boolean, px = 2) {
  const size = 22 * px;
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d")!;
  g.scale(px, px);
  g.lineWidth = hollow ? 2.4 : 1.6;
  g.strokeStyle = hollow ? color : "#ffffff";
  g.fillStyle = color;
  g.beginPath();
  if (shape === "circle") g.arc(11, 11, 7, 0, Math.PI * 2);
  if (shape === "triangle") { g.moveTo(11, 3); g.lineTo(19, 18); g.lineTo(3, 18); g.closePath(); }
  if (shape === "diamond") { g.moveTo(11, 2.5); g.lineTo(19.5, 11); g.lineTo(11, 19.5); g.lineTo(2.5, 11); g.closePath(); }
  if (shape === "square") { g.roundRect(4, 4, 14, 14, 3); }
  if (shape === "hexagon") {
    for (let i = 0; i < 6; i++) {
      const a = -Math.PI / 2 + (i * Math.PI) / 3;
      const [x, y] = [11 + 8.2 * Math.cos(a), 11 + 8.2 * Math.sin(a)];
      if (i === 0) g.moveTo(x, y); else g.lineTo(x, y);
    }
    g.closePath();
  }
  if (!hollow) g.fill();
  else { g.fillStyle = "rgba(255,255,255,0.85)"; g.fill(); }
  g.stroke();
  return { width: size, height: size, data: new Uint8Array(g.getImageData(0, 0, size, size).data.buffer) };
}

function iconId(t: RecordType, color: string, hollow: boolean) {
  return `ap|${TYPE_SHAPES[t]}|${color}|${hollow ? "h" : "f"}`;
}

function eventsToGeoJSON(events: MapEvent[], [from, to]: [number, number]) {
  const inRange = events.filter((e) => e.year == null || (e.year >= from && e.year <= to));
  const exact = inRange.filter((e) => e.precision === "street");
  const approx = inRange.filter((e) => isApproximate(e.precision));
  const pt = (e: MapEvent, hollow: boolean) => ({
    type: "Feature" as const,
    id: e.id,
    geometry: { type: "Point" as const, coordinates: [e.lng, e.lat] },
    properties: { id: e.id, icon: iconId(e.recordType, markerColor(e.recordType, e.cause), hollow), year: e.year },
  });
  return {
    exact: { type: "FeatureCollection" as const, features: exact.map((e) => pt(e, false)) },
    approxPts: { type: "FeatureCollection" as const, features: approx.map((e) => pt(e, true)) },
    approxAreas: {
      type: "FeatureCollection" as const,
      features: approx.map((e) => ({
        type: "Feature" as const,
        geometry: { type: "Polygon" as const, coordinates: [circleRing(e.lng, e.lat, siteConfig.check.approximateRadiusM)] },
        properties: { id: e.id, color: markerColor(e.recordType, e.cause) },
      })),
    },
  };
}

export default function PropertyMap(props: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const cityMarkers = useRef<maplibregl.Marker[]>([]);
  const searchMarker = useRef<maplibregl.Marker | null>(null);
  const latest = useRef(props);
  latest.current = props;
  const styleDark = useRef(props.dark);

  // ── init once ─────────────────────────────────────────────
  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: props.dark ? siteConfig.map.styleDark : siteConfig.map.styleLight,
      center: siteConfig.map.center,
      zoom: siteConfig.map.zoom,
      maxBounds: [
        [siteConfig.bounds[0] - 1, siteConfig.bounds[1] - 1],
        [siteConfig.bounds[2] + 1, siteConfig.bounds[3] + 1],
      ],
      attributionControl: { compact: true },
      cooperativeGestures: false,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.getCanvas().setAttribute("aria-label", props.labels.region);
    map.getCanvas().setAttribute("role", "region");

    // Pre-register every marker icon (shape × color × filled/hollow). Re-run after each style swap.
    const addIcons = () => {
      const combos = new Set<string>();
      for (const c of CAUSES) for (const h of [false, true]) combos.add(iconId("death", markerColor("death", c), h));
      for (const t of RECORD_TYPES) for (const h of [false, true]) combos.add(iconId(t, markerColor(t, "unknown"), h));
      for (const id of combos) {
        if (map.hasImage(id)) continue;
        const [, shape, color, fill] = id.split("|");
        map.addImage(id, makeIcon(shape as Shape, color, fill === "h"), { pixelRatio: 2 });
      }
    };

    const addLayers = () => {
      addIcons();
      const empty = { type: "FeatureCollection" as const, features: [] };
      if (!map.getSource("search")) {
        map.addSource("search", { type: "geojson", data: empty });
        map.addSource("approx-areas", { type: "geojson", data: empty });
        map.addSource("approx-pts", { type: "geojson", data: empty });
        map.addSource("exact", { type: "geojson", data: empty, cluster: true, clusterRadius: 44, clusterMaxZoom: 15 });

        map.addLayer({ id: "search-fill", type: "fill", source: "search", paint: { "fill-color": "#3d6957", "fill-opacity": 0.06 } });
        map.addLayer({ id: "search-line", type: "line", source: "search", paint: { "line-color": "#3d6957", "line-width": 1.5, "line-dasharray": [2, 2] } });
        map.addLayer({ id: "approx-fill", type: "fill", source: "approx-areas", paint: { "fill-color": ["get", "color"], "fill-opacity": 0.14 } });
        map.addLayer({ id: "approx-line", type: "line", source: "approx-areas", paint: { "line-color": ["get", "color"], "line-width": 1.2, "line-opacity": 0.6, "line-dasharray": [1.5, 1.5] } });
        map.addLayer({ id: "approx-icon", type: "symbol", source: "approx-pts", layout: { "icon-image": ["get", "icon"], "icon-size": 0.9, "icon-allow-overlap": true } });
        map.addLayer({
          id: "clusters", type: "circle", source: "exact", filter: ["has", "point_count"],
          paint: {
            "circle-color": "#fffdf9", "circle-stroke-color": "#3d6957", "circle-stroke-width": 2,
            "circle-radius": ["step", ["get", "point_count"], 14, 5, 18, 20, 24],
          },
        });
        map.addLayer({
          id: "cluster-count", type: "symbol", source: "exact", filter: ["has", "point_count"],
          layout: { "text-field": ["get", "point_count_abbreviated"], "text-size": 12, "text-font": ["Noto Sans Bold"] },
          paint: { "text-color": "#29241f" },
        });
        map.addLayer({
          id: "exact-icon", type: "symbol", source: "exact", filter: ["!", ["has", "point_count"]],
          layout: { "icon-image": ["get", "icon"], "icon-allow-overlap": true, "icon-size": 1 },
        });
      }
      sync();
    };

    const sync = () => {
      const p = latest.current;
      const gj = eventsToGeoJSON(p.events, p.years);
      (map.getSource("exact") as GeoJSONSource | undefined)?.setData(gj.exact);
      (map.getSource("approx-pts") as GeoJSONSource | undefined)?.setData(gj.approxPts);
      (map.getSource("approx-areas") as GeoJSONSource | undefined)?.setData(gj.approxAreas);
      const s = p.searched;
      (map.getSource("search") as GeoJSONSource | undefined)?.setData(
        s
          ? { type: "Feature", geometry: { type: "Polygon", coordinates: [circleRing(s.lng, s.lat, p.radiusM)] }, properties: {} }
          : { type: "FeatureCollection", features: [] },
      );
    };
    (map as unknown as { __apSync: () => void }).__apSync = sync;

    // Fires for the first style and again after every setStyle (theme swap)
    map.on("style.load", addLayers);

    const emitBounds = () => {
      const b = map.getBounds();
      latest.current.onBounds([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
    };
    map.on("moveend", emitBounds);
    map.once("load", emitBounds);

    map.on("click", async (e) => {
      const layers = ["clusters", "exact-icon", "approx-icon", "approx-fill"].filter((l) => map.getLayer(l));
      const hits = map.queryRenderedFeatures(e.point, { layers });
      const top = hits[0];
      if (top?.layer.id === "clusters") {
        const src = map.getSource("exact") as GeoJSONSource;
        const zoom = await src.getClusterExpansionZoom(top.properties.cluster_id as number);
        map.easeTo({ center: (top.geometry as unknown as { coordinates: [number, number] }).coordinates, zoom });
        return;
      }
      if (top?.properties?.id) {
        latest.current.onSelect(String(top.properties.id));
        return;
      }
      latest.current.onPick(e.lngLat.lat, e.lngLat.lng);
    });
    for (const l of ["clusters", "exact-icon", "approx-icon"]) {
      map.on("mouseenter", l, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", l, () => (map.getCanvas().style.cursor = ""));
    }

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── data / years / search ring ───────────────────────────
  useEffect(() => {
    const map = mapRef.current as (MLMap & { __apSync?: () => void }) | null;
    if (map?.isStyleLoaded()) map.__apSync?.();
  }, [props.events, props.years, props.searched, props.radiusM]);

  // ── searched-location pin ────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    searchMarker.current?.remove();
    searchMarker.current = null;
    if (props.searched) {
      const el = document.createElement("div");
      el.setAttribute("aria-hidden", "true");
      el.innerHTML = `<svg width="30" height="38" viewBox="0 0 30 38"><path d="M15 37s12-12.6 12-22A12 12 0 0 0 3 15c0 9.4 12 22 12 22Z" fill="#a35f3d" stroke="#fffdf9" stroke-width="2"/><circle cx="15" cy="15" r="4.5" fill="#fffdf9"/></svg>`;
      searchMarker.current = new maplibregl.Marker({ element: el, anchor: "bottom" }).setLngLat([props.searched.lng, props.searched.lat]).addTo(map);
    }
  }, [props.searched]);

  // ── city-only badges (filtered by the timeline) ──────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    cityMarkers.current.forEach((m) => m.remove());
    cityMarkers.current = [];
    const [from, to] = props.years;
    const byCity = new Map<string, { n: number; lat: number; lng: number }>();
    for (const b of props.cities) {
      if (b.decade + 9 < from || b.decade > to) continue;
      const cur = byCity.get(b.city) ?? { n: 0, lat: b.lat, lng: b.lng };
      cur.n += b.n;
      byCity.set(b.city, cur);
    }
    for (const [city, v] of byCity) {
      const el = document.createElement("button");
      el.type = "button";
      el.className =
        "rounded-full border border-line bg-surface/95 px-2.5 py-1 text-xs font-medium text-ink shadow-card hover:border-accent";
      el.textContent = `${city} · ${v.n}`;
      el.setAttribute("aria-label", props.labels.cityBadge(city, v.n));
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        latest.current.onCity(city, v.lat, v.lng);
      });
      // Offset badges below the town center so they don't sit on top of street-level pins
      cityMarkers.current.push(new maplibregl.Marker({ element: el, offset: [0, 26] }).setLngLat([v.lng, v.lat]).addTo(map));
    }
  }, [props.cities, props.years, props.labels]);

  // ── theme swap ───────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || styleDark.current === props.dark) return;
    styleDark.current = props.dark;
    map.setStyle(props.dark ? siteConfig.map.styleDark : siteConfig.map.styleLight);
  }, [props.dark]);

  // ── fly to a searched place ──────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !props.flyTo) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const opts = { center: [props.flyTo.lng, props.flyTo.lat] as [number, number], zoom: props.flyTo.zoom ?? 16 };
    if (reduce) map.jumpTo(opts);
    else map.flyTo({ ...opts, speed: 1.4, essential: true });
  }, [props.flyTo]);

  // ── highlight the selected record ────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded() || !map.getLayer("exact-icon")) return;
    const id = props.selectedId ?? "";
    map.setLayoutProperty("exact-icon", "icon-size", ["case", ["==", ["get", "id"], id], 1.45, 1]);
    map.setLayoutProperty("approx-icon", "icon-size", ["case", ["==", ["get", "id"], id], 1.3, 0.9]);
  }, [props.selectedId]);

  return (
    <div className="absolute inset-0">
      <div ref={container} className="h-full w-full" />
    </div>
  );
}
