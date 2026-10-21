"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useTheme } from "@/components/ui/Header";
import { defaultFilters, filtersToQuery } from "@/lib/filters";
import { siteConfig } from "@/site.config";
import type { Bbox, CityBucket, MapEvent } from "@/lib/types";

const PropertyMap = dynamic(() => import("@/components/map/PropertyMap"), { ssr: false });

/** Read-only overview map for an area page. Same public data as the main map. */
export function AreaMap({ center, zoom }: { center: [number, number]; zoom: number }) {
  const t = useTranslations();
  const { dark } = useTheme();
  const [bbox, setBbox] = useState<Bbox | null>(null);
  const [events, setEvents] = useState<MapEvent[]>([]);
  const [cities, setCities] = useState<CityBucket[]>([]);
  const fly = useMemo(() => ({ lat: center[1], lng: center[0], zoom, key: 1 }), [center, zoom]);

  useEffect(() => {
    if (!bbox) return;
    const qs = new URLSearchParams({ bbox: bbox.map((n) => n.toFixed(4)).join(","), ...filtersToQuery(defaultFilters) });
    fetch(`/api/map?${qs}`).then((r) => r.json()).then((j) => { setEvents(j.events ?? []); setCities(j.cities ?? []); }).catch(() => undefined);
  }, [bbox]);

  const labels = useMemo(() => ({
    region: t("area.byDecade"),
    approx: t("legend.approx"),
    cityBadge: (c: string, n: number) => `${c}: ${n}`,
    cluster: (n: number) => String(n),
  }), [t]);

  return (
    <PropertyMap
      events={events}
      cities={cities}
      years={[siteConfig.timeline.startYear, new Date().getFullYear()]}
      dark={dark}
      searched={null}
      radiusM={0}
      selectedId={null}
      flyTo={fly}
      labels={labels}
      onBounds={setBbox}
      onSelect={() => undefined}
      onPick={() => undefined}
      onCity={() => undefined}
    />
  );
}
