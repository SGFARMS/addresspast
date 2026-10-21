"use client";

import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { X } from "lucide-react";
import { CAUSES, RECORD_TYPES, type Cause, type MapFilters, type RecordType } from "@/lib/types";
import { defaultFilters } from "@/lib/filters";
import { ShapeIcon, TYPE_SHAPES, markerColor, useRecordLabels } from "@/components/records/bits";

interface Props {
  open: boolean;
  value: MapFilters;
  onChange: (f: MapFilters) => void;
  onClose: () => void;
}

export function FilterPanel({ open, value, onChange, onClose }: Props) {
  const t = useTranslations("filters");
  const l = useRecordLabels();
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  const toggleType = (rt: RecordType) => {
    const has = value.recordTypes.includes(rt);
    const next = has ? value.recordTypes.filter((x) => x !== rt) : [...value.recordTypes, rt];
    onChange({ ...value, recordTypes: next.length ? next : [rt] });
  };
  const toggleCause = (c: Cause) => {
    const cur = value.causes ?? CAUSES.filter((x) => x !== "natural" || value.includeNatural);
    const next = cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c];
    onChange({ ...value, causes: next.length === CAUSES.length || next.length === 0 ? null : next, includeNatural: c === "natural" ? next.includes("natural") : value.includeNatural });
  };
  const causeOn = (c: Cause) => (c === "natural" ? value.includeNatural && (!value.causes || value.causes.includes(c)) : !value.causes || value.causes.includes(c));

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      aria-labelledby="filters-title"
      className="m-auto w-[min(92vw,440px)] rounded-2xl border border-line bg-surface p-0 text-ink shadow-card backdrop:bg-black/40"
    >
      <div className="flex items-center justify-between border-b border-line px-5 py-4">
        <h2 id="filters-title" className="font-serif text-lg font-semibold">{t("title")}</h2>
        <button type="button" onClick={onClose} aria-label={t("done")} className="rounded-md p-1.5 text-ink-2 hover:bg-surface-2">
          <X size={18} aria-hidden />
        </button>
      </div>
      <div className="max-h-[70vh] space-y-6 overflow-y-auto px-5 py-5">
        <fieldset>
          <legend className="mb-2 text-sm font-semibold">{t("recordTypes")}</legend>
          <div className="grid grid-cols-2 gap-2">
            {RECORD_TYPES.map((rt) => (
              <label key={rt} className="flex cursor-pointer items-center gap-2 rounded-lg border border-line px-3 py-2 text-sm has-[:checked]:border-accent has-[:checked]:bg-accent-soft">
                <input type="checkbox" className="accent-[var(--accent)]" checked={value.recordTypes.includes(rt)} onChange={() => toggleType(rt)} />
                <ShapeIcon shape={TYPE_SHAPES[rt]} color={markerColor(rt, "unknown")} />
                {l.type(rt)}
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className="mb-2 text-sm font-semibold">{t("causes")}</legend>
          <div className="flex flex-wrap gap-2">
            {CAUSES.map((c) => (
              <label key={c} className="flex cursor-pointer items-center gap-2 rounded-full border border-line px-3 py-1.5 text-sm has-[:checked]:border-accent has-[:checked]:bg-accent-soft">
                <input type="checkbox" className="accent-[var(--accent)]" checked={causeOn(c)} onChange={() => toggleCause(c)} />
                <ShapeIcon shape="circle" color={markerColor("death", c)} size={12} />
                {l.cause(c)}
              </label>
            ))}
          </div>
        </fieldset>

        <div>
          <label className="flex items-start gap-3 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 accent-[var(--accent)]"
              checked={value.includeNatural}
              onChange={(e) => onChange({ ...value, includeNatural: e.target.checked, causes: value.causes && e.target.checked ? [...value.causes, "natural"] : value.causes?.filter((c) => c !== "natural") ?? null })}
            />
            <span>
              <span className="font-semibold">{t("includeNatural")}</span>
              <span className="mt-1 block text-xs text-ink-2">{t("naturalNote")}</span>
            </span>
          </label>
        </div>

        <fieldset>
          <legend className="mb-2 text-sm font-semibold">{t("minConfidence")}</legend>
          <div className="flex gap-2">
            {[0, 0.5, 0.75].map((v) => (
              <label key={v} className="flex-1 cursor-pointer rounded-lg border border-line px-3 py-2 text-center text-sm has-[:checked]:border-accent has-[:checked]:bg-accent-soft has-[:focus-visible]:outline-2">
                <input type="radio" name="minConf" className="sr-only" checked={value.minConfidence === v} onChange={() => onChange({ ...value, minConfidence: v })} />
                {v === 0 ? t("any") : v === 0.5 ? <MediumPlus /> : <High />}
              </label>
            ))}
          </div>
        </fieldset>

        <label className="flex items-center gap-3 text-sm">
          <input type="checkbox" className="accent-[var(--accent)]" checked={value.verifiedOnly} onChange={(e) => onChange({ ...value, verifiedOnly: e.target.checked })} />
          <span className="font-semibold">{t("verifiedOnly")}</span>
        </label>
      </div>
      <div className="flex justify-between border-t border-line px-5 py-3">
        <button type="button" onClick={() => onChange(defaultFilters)} className="rounded-lg px-3 py-2 text-sm text-ink-2 hover:bg-surface-2">
          {t("reset")}
        </button>
        <button type="button" onClick={onClose} className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-ink">
          {t("done")}
        </button>
      </div>
    </dialog>
  );
}

function MediumPlus() {
  const t = useTranslations("record");
  return <>{t("medium")}+</>;
}
function High() {
  const t = useTranslations("record");
  return <>{t("high")}</>;
}
