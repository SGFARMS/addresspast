"use client";

import { useTranslations } from "next-intl";
import { BadgeCheck, Info } from "lucide-react";
import { siteConfig } from "@/site.config";
import { confidenceBand, isApproximate } from "@/lib/format";
import type { Cause, GeoPrecision, RecordType } from "@/lib/types";

export const TYPE_COLORS: Record<RecordType, string> = {
  death: "#5E6B78",
  road_death: "#9A5B3C",
  fire: "#B08A47",
  drug_lab: "#7A6780",
  flood_zone: "#4F7FA0",
};

export const TYPE_SHAPES: Record<RecordType, "circle" | "triangle" | "diamond" | "square" | "hexagon"> = {
  death: "circle",
  road_death: "hexagon",
  fire: "triangle",
  drug_lab: "diamond",
  flood_zone: "square",
};

export function markerColor(recordType: RecordType, cause: Cause) {
  return recordType === "death" ? siteConfig.causeColors[cause] ?? siteConfig.causeColors.unknown : TYPE_COLORS[recordType];
}

export function ShapeIcon({ shape, color, size = 14, hollow = false }: { shape: string; color: string; size?: number; hollow?: boolean }) {
  const s = size;
  const common = { fill: hollow ? "none" : color, stroke: color, strokeWidth: hollow ? 2 : 1.5 };
  return (
    <svg width={s} height={s} viewBox="0 0 16 16" aria-hidden focusable="false" className="shrink-0">
      {shape === "circle" && <circle cx="8" cy="8" r="6" {...common} />}
      {shape === "triangle" && <path d="M8 2 14.5 13.5h-13Z" {...common} strokeLinejoin="round" />}
      {shape === "diamond" && <path d="M8 1.5 14.5 8 8 14.5 1.5 8Z" {...common} strokeLinejoin="round" />}
      {shape === "square" && <rect x="2.5" y="2.5" width="11" height="11" rx="2" {...common} />}
      {shape === "hexagon" && <path d="M8 1.5 13.6 4.75v6.5L8 14.5 2.4 11.25v-6.5Z" {...common} strokeLinejoin="round" />}
    </svg>
  );
}

export function useRecordLabels() {
  const types = useTranslations("types");
  const causes = useTranslations("causes");
  const precision = useTranslations("precision");
  return {
    type: (t: RecordType) => types(t),
    cause: (c: Cause) => causes(c),
    precision: (p: GeoPrecision) => precision(p, { radius: siteConfig.check.approximateRadiusM }),
    /** "Homicide" for deaths, "Structure fire" for other layers */
    category: (t: RecordType, c: Cause) => (t === "death" ? causes(c) : types(t)),
  };
}

export function PrecisionBadge({ precision }: { precision: GeoPrecision }) {
  const l = useRecordLabels();
  const approx = isApproximate(precision);
  const city = precision === "city";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${
        approx
          ? "border-adobe/40 bg-adobe-soft text-ink"
          : city
            ? "border-line bg-surface-2 text-ink-2"
            : "border-accent/30 bg-accent-soft text-ink"
      }`}
    >
      {approx && <Info size={12} aria-hidden />}
      {l.precision(precision)}
    </span>
  );
}

export function ConfidenceMeter({ value }: { value: number }) {
  const t = useTranslations("record");
  const band = confidenceBand(value);
  const filled = band === "high" ? 3 : band === "medium" ? 2 : 1;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-ink-2" title={`${t("confidence")}: ${Math.round(value * 100)}%`}>
      <span className="flex gap-0.5" aria-hidden>
        {[1, 2, 3].map((i) => (
          <span key={i} className={`h-2 w-3.5 rounded-sm ${i <= filled ? "bg-accent" : "bg-line"}`} />
        ))}
      </span>
      <span>
        <span className="sr-only">{t("confidence")}: </span>
        {t(band)}
      </span>
    </span>
  );
}

export function VerifiedBadge() {
  const t = useTranslations("record");
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-accent" title={t("verifiedHelp")}>
      <BadgeCheck size={14} aria-hidden />
      {t("verified")}
    </span>
  );
}

export function Disclaimer({ className = "" }: { className?: string }) {
  const t = useTranslations();
  return <p className={`text-xs leading-relaxed text-ink-3 ${className}`}>{t("disclaimer")}</p>;
}
