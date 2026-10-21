"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Layers } from "lucide-react";
import type { MapFilters } from "@/lib/types";
import { CAUSES } from "@/lib/types";
import { ShapeIcon, TYPE_SHAPES, markerColor, useRecordLabels } from "@/components/records/bits";

export function Legend({ filters }: { filters: MapFilters }) {
  const t = useTranslations("legend");
  const l = useRecordLabels();
  const [open, setOpen] = useState(false);
  const causes = CAUSES.filter((c) => (c !== "natural" || filters.includeNatural) && (!filters.causes || filters.causes.includes(c)));

  return (
    <div className="pointer-events-auto flex flex-col-reverse items-end gap-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-xl border border-line bg-surface/95 px-3 py-2 text-xs font-medium text-ink shadow-card backdrop-blur hover:border-accent"
      >
        <Layers size={14} aria-hidden /> {t("title")}
      </button>
      {open && (
        <div className="w-60 space-y-3 rounded-xl border border-line bg-surface/95 p-3 text-xs shadow-card backdrop-blur">
          {filters.recordTypes.includes("death") && (
            <ul className="space-y-1.5">
              {causes.map((c) => (
                <li key={c} className="flex items-center gap-2">
                  <ShapeIcon shape="circle" color={markerColor("death", c)} /> {l.cause(c)}
                </li>
              ))}
            </ul>
          )}
          {filters.recordTypes.filter((r) => r !== "death").length > 0 && (
            <ul className="space-y-1.5 border-t border-line pt-2">
              {filters.recordTypes.filter((r) => r !== "death").map((r) => (
                <li key={r} className="flex items-center gap-2">
                  <ShapeIcon shape={TYPE_SHAPES[r]} color={markerColor(r, "unknown")} /> {l.type(r)}
                </li>
              ))}
            </ul>
          )}
          <ul className="space-y-1.5 border-t border-line pt-2 text-ink-2">
            <li className="flex items-center gap-2"><ShapeIcon shape="circle" color="#5E6B78" /> {t("exact")}</li>
            <li className="flex items-center gap-2"><ShapeIcon shape="circle" color="#5E6B78" hollow /> {t("approx")}</li>
            <li className="flex items-center gap-2"><span className="rounded-full border border-line px-1.5 text-[10px]">Belen · 3</span> {t("city")}</li>
            <li className="flex items-center gap-2"><span className="grid h-4 w-4 place-items-center rounded-full border-2 border-accent text-[9px] font-bold">5</span> {t("cluster")}</li>
          </ul>
        </div>
      )}
    </div>
  );
}
