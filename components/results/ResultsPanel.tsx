"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Building2, ChevronLeft, ExternalLink, History, Info, Newspaper, X } from "lucide-react";
import { siteConfig } from "@/site.config";
import { dateLabel, metersLabel, yearLabel } from "@/lib/format";
import { track } from "@/lib/analytics";
import type { CheckItem, EventDetail, FreeCheck, Place } from "@/lib/types";
import {
  ConfidenceMeter, Disclaimer, PrecisionBadge, ShapeIcon, TYPE_SHAPES, VerifiedBadge, markerColor, useRecordLabels,
} from "@/components/records/bits";
import { RemovalForm } from "@/components/records/RemovalForm";

interface Props {
  place: Place;
  check: FreeCheck | null;
  loading: boolean;
  error: string | null;
  includeNatural: boolean;
  onlyDeaths: boolean;
  recordTypes: string[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onToggleNatural: (on: boolean) => void;
  onClose: () => void;
}

export function ResultsPanel(p: Props) {
  const t = useTranslations("check");
  if (p.selectedId) return <RecordDetail id={p.selectedId} onBack={() => p.onSelect(null)} />;
  return (
    <section aria-labelledby="results-heading" aria-busy={p.loading} className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("heading")}</p>
          <h2 id="results-heading" className="truncate font-serif text-lg font-semibold">{p.place.label}</h2>
        </div>
        <button type="button" onClick={p.onClose} aria-label={t("close")} className="rounded-md p-1.5 text-ink-2 hover:bg-surface-2">
          <X size={18} aria-hidden />
        </button>
      </div>
      {p.loading && <CheckSkeleton label={t("loading")} />}
      {p.error && !p.loading && <p role="alert" className="rounded-xl bg-adobe-soft p-3 text-sm">{p.error}</p>}
      {p.check && !p.loading && <FreeCheckCard {...p} check={p.check} />}
      <Disclaimer />
    </section>
  );
}

function CheckSkeleton({ label }: { label: string }) {
  return (
    <div className="space-y-3" role="status">
      <span className="sr-only">{label}</span>
      <div className="skeleton h-20 w-full" />
      <div className="skeleton h-14 w-full" />
      <div className="skeleton h-14 w-full" />
    </div>
  );
}

function FreeCheckCard({ check, includeNatural, onlyDeaths, recordTypes, onSelect, onToggleNatural, place }: Props & { check: FreeCheck }) {
  const t = useTranslations("check");
  const locale = useLocale();
  const radius = metersLabel(siteConfig.check.nearbyRadiusM, locale);
  const shown = (i: CheckItem) => includeNatural || i.cause !== "natural";
  const at = check.atAddress.filter(shown);
  const near = check.nearby.filter(shown);
  const hiddenNatural = includeNatural ? 0 : [...check.atAddress, ...check.nearby].filter((i) => i.cause === "natural").length;
  const none = at.length === 0 && near.length === 0;
  const asOf = dateLabel(check.asOf, locale) ?? dateLabel(new Date().toISOString(), locale)!;
  const cov = check.coverage;

  useEffect(() => {
    track("free_check", { found: !none, at: at.length, near: near.length });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [check]);

  return (
    <>
      <div className={`rounded-2xl border p-4 ${none ? "border-accent/30 bg-accent-soft/60" : "border-line bg-surface-2/60"}`} aria-live="polite">
        {none ? (
          <p className="font-serif text-[1.05rem] font-semibold leading-snug">{onlyDeaths ? t("noneTitle") : t("noneTitleOther")}</p>
        ) : (
          <p className="font-serif text-[1.05rem] font-semibold leading-snug">
            {t("atAddress", { count: at.length })} <span className="text-ink-3">·</span> {t("nearby", { count: near.length, radius })}
          </p>
        )}
        <p className="mt-2 text-sm text-ink-2">
          {cov && cov.firstYear && cov.lastYear
            ? t("searched", { sources: cov.sourceCount, from: cov.firstYear, to: cov.lastYear, county: cov.county, date: asOf })
            : t("searchedGeneric", { date: asOf })}{" "}
          {t("gapNote")}
        </p>
        {hiddenNatural > 0 && (
          <p className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <span className="text-ink-2">{t("naturalHidden", { count: hiddenNatural })}</span>
            <button type="button" onClick={() => onToggleNatural(true)} className="font-medium text-accent underline-offset-2 hover:underline">
              {t("show")}
            </button>
          </p>
        )}
        {includeNatural && [...check.atAddress, ...check.nearby].some((i) => i.cause === "natural") && (
          <button type="button" onClick={() => onToggleNatural(false)} className="mt-2 text-sm font-medium text-accent hover:underline">
            {t("hide")}
          </button>
        )}
        {check.cityOnlyCount > 0 && place.city && place.kind !== "area" && (
          <p className="mt-2 flex gap-1.5 text-sm text-ink-2">
            <Info size={16} className="mt-0.5 shrink-0" aria-hidden />
            {t("cityOnly", { count: check.cityOnlyCount, city: place.city })}
          </p>
        )}
        {check.parcelMatched && <p className="mt-2 text-xs text-ink-3">{t("parcel")}</p>}
        {check.parcelYearBuilt && (
          <p className="mt-2 flex gap-1.5 text-sm text-ink-2">
            <History size={16} className="mt-0.5 shrink-0" aria-hidden />
            <span>
              {t("builtIn", { year: check.parcelYearBuilt })}{" "}
              {at.some((i) => i.predatesBuilding) && t("olderThanBuilding", { count: at.filter((i) => i.predatesBuilding).length })}
            </span>
          </p>
        )}
      </div>

      {at.length > 0 && <RecordList title={t("atThisAddress")} items={at} onSelect={onSelect} />}
      {near.length > 0 && <RecordList title={t("nearbyHeading")} items={near} onSelect={onSelect} showDistance />}
      {place.city && (check.cityOnlyCount > 0 || place.kind === "area") && (
        <TownRecords
          city={place.city}
          autoOpen={place.kind === "area"}
          includeNatural={includeNatural}
          recordTypes={recordTypes}
          onSelect={onSelect}
        />
      )}
    </>
  );
}

/** Records placed only at town level ("Gallup, 1912"): a list behind a button, or open straight away
 *  when the person tapped the town's badge on the map. */
function TownRecords({ city, autoOpen, includeNatural, recordTypes, onSelect }: {
  city: string; autoOpen: boolean; includeNatural: boolean; recordTypes: string[]; onSelect: (id: string) => void;
}) {
  const t = useTranslations("check");
  const [open, setOpen] = useState(autoOpen);
  const [items, setItems] = useState<CheckItem[] | null>(null);
  const [failed, setFailed] = useState(false);
  const key = `${city}|${includeNatural}|${recordTypes.join(",")}`;

  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    setItems(null);
    setFailed(false);
    const qs = new URLSearchParams({ city, natural: includeNatural ? "1" : "0", types: recordTypes.join(",") });
    fetch(`/api/city?${qs}`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((j: { items: CheckItem[] }) => setItems(j.items))
      .catch((e: Error) => { if (e.name !== "AbortError") setFailed(true); });
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, key]);

  if (!open) {
    return (
      <button type="button" onClick={() => { track("town_list_open"); setOpen(true); }}
        className="self-start rounded-xl border border-line bg-surface px-3 py-2 text-sm font-medium hover:border-accent">
        {t("townShow", { city })}
      </button>
    );
  }
  if (failed) return <p role="alert" className="rounded-xl bg-adobe-soft p-3 text-sm">{t("townFailed")}</p>;
  if (!items) return <CheckSkeleton label={t("townLoading", { city })} />;
  if (items.length === 0) return <p className="text-sm text-ink-2">{t("townNone", { city })}</p>;
  return <RecordList title={t("townHeading", { city, count: items.length })} items={items} onSelect={onSelect} />;
}

function RecordList({ title, items, onSelect, showDistance }: { title: string; items: CheckItem[]; onSelect: (id: string) => void; showDistance?: boolean }) {
  const t = useTranslations();
  const locale = useLocale();
  const l = useRecordLabels();
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-3">{title}</h3>
      <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
        {items.map((i) => (
          <li key={i.id}>
            <button
              type="button"
              onClick={() => { track("record_open"); onSelect(i.id); }}
              className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-surface-2"
            >
              <span className="mt-1"><ShapeIcon shape={TYPE_SHAPES[i.recordType]} color={markerColor(i.recordType, i.cause)} hollow={i.precision !== "street"} /></span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-baseline gap-x-2">
                  <span className="font-semibold tabular-nums">{yearLabel(i.year, i.datePrecision) ?? t("check.noYear")}</span>
                  <span className="text-ink-2">{l.category(i.recordType, i.cause)}</span>
                  {i.recordType === "death" && <span className="sr-only">{l.type(i.recordType)}</span>}
                </span>
                <span className="mt-1.5 flex flex-wrap items-center gap-2">
                  <PrecisionBadge precision={i.precision} />
                  {i.verified && <VerifiedBadge />}
                  {i.buildingLevel && <Chip icon="building">{t("record.buildingLevel")}</Chip>}
                  {i.predatesBuilding && <Chip icon="history">{t("record.predates")}</Chip>}
                  {showDistance && <span className="text-xs text-ink-3">{t("record.distance", { distance: metersLabel(i.distanceM, locale) })}</span>}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RecordDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const t = useTranslations("record");
  const locale = useLocale();
  const l = useRecordLabels();
  const [d, setD] = useState<EventDetail | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let live = true;
    setD(null);
    setErr(false);
    fetch(`/api/events/${id}?locale=${locale}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((j) => live && setD(j))
      .catch(() => live && setErr(true));
    return () => { live = false; };
  }, [id, locale]);

  return (
    <section aria-labelledby="record-heading" className="flex flex-col gap-4">
      <button type="button" onClick={onBack} className="flex w-fit items-center gap-1 rounded-md py-1 pr-2 text-sm text-ink-2 hover:text-ink">
        <ChevronLeft size={16} aria-hidden /> {t("back")}
      </button>
      {!d && !err && (
        <div className="space-y-3" role="status"><span className="sr-only">{t("loading")}</span><div className="skeleton h-8 w-2/3" /><div className="skeleton h-24" /></div>
      )}
      {err && <p role="alert" className="text-sm">{t("loading")}</p>}
      {d && (
        <>
          <div>
            <h2 id="record-heading" className="flex items-center gap-2 font-serif text-xl font-semibold">
              <ShapeIcon shape={TYPE_SHAPES[d.recordType]} color={markerColor(d.recordType, d.cause)} size={16} hollow={d.precision !== "street"} />
              <span className="tabular-nums">{yearLabel(d.year, d.datePrecision)}</span>
              <span className="font-normal text-ink-2">· {l.category(d.recordType, d.cause)}</span>
            </h2>
            <p className="mt-1 text-sm text-ink-3">{[d.city, d.county && `${d.county} County`].filter(Boolean).join(", ")}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <PrecisionBadge precision={d.precision} />
            <ConfidenceMeter value={d.confidence} />
            {d.verified && <VerifiedBadge />}
          </div>
          {(d.buildingLevel || (d.parcelYearBuilt && d.year && d.year < d.parcelYearBuilt)) && (
            <ul className="space-y-1.5 text-sm text-ink-2">
              {d.buildingLevel && (
                <li className="flex gap-1.5"><Building2 size={16} className="mt-0.5 shrink-0" aria-hidden />{t("buildingLevelHelp")}</li>
              )}
              {d.parcelYearBuilt && d.year && d.year < d.parcelYearBuilt && (
                <li className="flex gap-1.5"><History size={16} className="mt-0.5 shrink-0" aria-hidden />{t("predatesHelp", { built: d.parcelYearBuilt, year: d.year })}</li>
              )}
            </ul>
          )}
          {d.summary ? (
            <p className="rounded-2xl border border-line bg-surface-2/50 p-4 leading-relaxed">{d.summary}</p>
          ) : (
            <p className="rounded-2xl border border-dashed border-line p-4 text-sm text-ink-2">{t("locked")}</p>
          )}
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("sources", { count: d.sources.length })}</h3>
            <ul className="space-y-2">
              {d.sources.map((s, i) => (
                <li key={i} className="rounded-xl border border-line bg-surface px-3 py-2.5 text-sm">
                  <p className="font-medium">{s.name}</p>
                  {s.published && <p className="text-xs text-ink-3">{t("published", { date: dateLabel(s.published, locale) ?? s.published })}</p>}
                  {s.url && (
                    <a href={s.url} target="_blank" rel="noopener noreferrer" className="mt-1.5 inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:underline">
                      {s.isLocScan ? <Newspaper size={15} aria-hidden /> : <ExternalLink size={15} aria-hidden />}
                      {s.isLocScan ? t("viewScan") : t("viewSource")}
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </div>
          <RemovalForm key={d.id} eventId={d.id} />
          <Disclaimer />
        </>
      )}
    </section>
  );
}

function Chip({ icon, children }: { icon: "building" | "history"; children: React.ReactNode }) {
  const Icon = icon === "building" ? Building2 : History;
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-line bg-surface-2 px-2 py-0.5 text-xs text-ink-2">
      <Icon size={12} aria-hidden />
      {children}
    </span>
  );
}
