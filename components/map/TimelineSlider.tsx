"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import type { CityBucket, MapEvent } from "@/lib/types";

interface Props {
  events: MapEvent[];
  cities: CityBucket[];
  min: number;
  max: number;
  value: [number, number];
  onChange: (v: [number, number]) => void;
}

/** 1860s → today, with a per-decade histogram. Filtering happens client-side, so it's instant. */
export function TimelineSlider({ events, cities, min, max, value, onChange }: Props) {
  const t = useTranslations("timeline");
  const decades = useMemo(() => {
    const start = Math.floor(min / 10) * 10;
    const counts = new Map<number, number>();
    for (let d = start; d <= max; d += 10) counts.set(d, 0);
    for (const e of events) if (e.year != null) {
      const d = Math.floor(e.year / 10) * 10;
      if (counts.has(d)) counts.set(d, counts.get(d)! + 1);
    }
    for (const c of cities) if (counts.has(c.decade)) counts.set(c.decade, counts.get(c.decade)! + c.n);
    return [...counts.entries()];
  }, [events, cities, min, max]);
  const peak = Math.max(1, ...decades.map(([, n]) => n));
  const [from, to] = value;
  const pct = (y: number) => ((y - min) / (max - min)) * 100;
  const all = from === min && to === max;

  return (
    <div className="rounded-2xl border border-line bg-surface/95 px-4 pb-3 pt-2 shadow-card backdrop-blur">
      <div className="mb-1 flex items-center justify-between text-xs">
        <span id="timeline-label" className="font-medium text-ink-2">
          {t("label")}: <span className="tabular-nums text-ink">{from}–{to}</span>
        </span>
        {!all && (
          <button type="button" onClick={() => onChange([min, max])} className="rounded px-1.5 py-0.5 text-accent hover:underline">
            {t("reset")}
          </button>
        )}
      </div>
      <div className="flex h-8 items-end gap-px" role="img" aria-label={t("histogram")}>
        {decades.map(([d, n]) => {
          const inside = d + 9 >= from && d <= to;
          return (
            <div
              key={d}
              title={`${d}s: ${n}`}
              className={`flex-1 rounded-t-sm ${inside ? "bg-accent/70" : "bg-line"}`}
              style={{ height: `${n ? Math.max(10, (n / peak) * 100) : 4}%` }}
            />
          );
        })}
      </div>
      <div className="relative h-7">
        <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded bg-line" />
        <div className="absolute top-1/2 h-1 -translate-y-1/2 rounded bg-accent" style={{ left: `${pct(from)}%`, right: `${100 - pct(to)}%` }} />
        <input
          type="range" className="range-dual" min={min} max={max} step={1} value={from}
          aria-label={t("from")} aria-describedby="timeline-label"
          onChange={(e) => onChange([Math.min(Number(e.target.value), to), to])}
        />
        <input
          type="range" className="range-dual" min={min} max={max} step={1} value={to}
          aria-label={t("to")} aria-describedby="timeline-label"
          onChange={(e) => onChange([from, Math.max(Number(e.target.value), from)])}
        />
      </div>
      <div className="flex justify-between text-[11px] tabular-nums text-ink-3">
        <span>{min}s</span>
        <span>1920</span>
        <span>1960</span>
        <span>2000</span>
        <span>{max}</span>
      </div>
    </div>
  );
}
