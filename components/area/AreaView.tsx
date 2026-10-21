import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { Header } from "@/components/ui/Header";
import type { AreaStats } from "@/lib/types";
import { CAUSES } from "@/lib/types";
import { siteConfig } from "@/site.config";
import { AreaMap } from "./AreaMap";

interface Props {
  locale: string;
  area: string;
  stats: AreaStats;
  summary: string;
  view: { center: [number, number]; zoom: number } | undefined;
  breadcrumbs: { href: string; label: string }[];
  children?: React.ReactNode;
}

/** Aggregate-only area page. No per-address content, ever. */
export async function AreaView({ locale, area, stats, summary, view, breadcrumbs, children }: Props) {
  const t = await getTranslations({ locale, namespace: "area" });
  const tc = await getTranslations({ locale, namespace: "causes" });
  const tp = await getTranslations({ locale, namespace: "precision" });
  const decades: number[] = [];
  for (let d = Math.floor(siteConfig.timeline.startYear / 10) * 10; d <= new Date().getFullYear(); d += 10) decades.push(d);
  const peak = Math.max(1, ...Object.values(stats.byDecade));
  const cov = stats.coverage;

  return (
    <div className="min-h-dvh">
      <Header />
      <main className="mx-auto max-w-5xl px-5 py-8 md:py-12">
        <nav aria-label="Breadcrumb" className="text-sm text-ink-3">
          <ol className="flex flex-wrap gap-1.5">
            {breadcrumbs.map((b, i) => (
              <li key={b.href} className="flex gap-1.5">
                {i > 0 && <span aria-hidden>/</span>}
                <Link href={b.href} className="hover:text-ink hover:underline">{b.label}</Link>
              </li>
            ))}
          </ol>
        </nav>
        <h1 className="mt-3 font-serif text-3xl font-semibold tracking-tight md:text-4xl">{t("title", { area })}</h1>
        <p className="mt-4 max-w-3xl text-lg leading-relaxed text-ink-2">{summary}</p>
        <p className="mt-2 text-xs text-ink-3">{t("aiNote")}</p>

        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          <Stat label={t("total", { count: stats.total })} value={stats.total.toLocaleString(locale)} />
          <Stat label={t("verified", { count: stats.verified })} value={stats.verified.toLocaleString(locale)} />
          <Stat
            label={t("coverage")}
            value={cov?.firstYear ? `${cov.firstYear}–${cov.lastYear}` : t("noCoverage")}
            sub={cov ? t("coverageText", { sources: cov.sourceCount, from: cov.firstYear ?? "", to: cov.lastYear ?? "" }) : undefined}
          />
        </div>

        <section className="mt-10" aria-labelledby="by-decade">
          <h2 id="by-decade" className="font-serif text-xl font-semibold">{t("byDecade")}</h2>
          <div className="mt-4 flex h-40 items-end gap-1 rounded-2xl border border-line bg-surface p-4">
            {decades.map((d) => {
              const n = stats.byDecade[String(d)] ?? 0;
              return (
                <div key={d} className="flex h-full flex-1 flex-col items-center justify-end gap-1">
                  <span className="text-[10px] tabular-nums text-ink-3">{n || ""}</span>
                  <div className={`w-full rounded-t ${n ? "bg-accent/70" : "bg-line"}`} style={{ height: `${n ? Math.max(6, (n / peak) * 100) : 2}%` }} title={`${d}s: ${n}`} />
                  <span className="hidden text-[10px] text-ink-3 sm:block">{d % 20 === 0 ? `${d}` : ""}</span>
                </div>
              );
            })}
          </div>
          <table className="sr-only">
            <caption>{t("byDecade")}</caption>
            <tbody>{decades.map((d) => <tr key={d}><th>{d}s</th><td>{stats.byDecade[String(d)] ?? 0}</td></tr>)}</tbody>
          </table>
        </section>

        <div className="mt-10 grid gap-8 md:grid-cols-2">
          <section aria-labelledby="by-cause">
            <h2 id="by-cause" className="font-serif text-xl font-semibold">{t("byCause")}</h2>
            <ul className="mt-3 divide-y divide-line rounded-2xl border border-line bg-surface">
              {CAUSES.filter((c) => c !== "natural").map((c) => (
                <li key={c} className="flex justify-between px-4 py-2.5 text-sm">
                  <span>{tc(c)}</span>
                  <span className="tabular-nums text-ink-2">{stats.byCause[c] ?? 0}</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-ink-3">{t("naturalExcluded")}</p>
          </section>
          <section aria-labelledby="by-precision">
            <h2 id="by-precision" className="font-serif text-xl font-semibold">{t("byPrecision")}</h2>
            <ul className="mt-3 divide-y divide-line rounded-2xl border border-line bg-surface">
              {(["street", "street_historic", "intersection", "landmark", "city"] as const).map((p) => (
                <li key={p} className="flex justify-between gap-4 px-4 py-2.5 text-sm">
                  <span>{tp(p, { radius: siteConfig.check.approximateRadiusM })}</span>
                  <span className="tabular-nums text-ink-2">{stats.byPrecision[p] ?? 0}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>

        {view && (
          <section className="mt-10">
            <div className="relative h-80 overflow-hidden rounded-2xl border border-line">
              <AreaMap center={view.center} zoom={view.zoom} />
            </div>
          </section>
        )}

        {children}

        <div className="mt-10 rounded-2xl border border-accent/30 bg-accent-soft/60 p-5">
          <p className="text-sm text-ink-2">{t("aggregateNote")}</p>
          <Link href="/" className="mt-3 inline-block rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-accent-ink">
            {t("checkAddress", { area })}
          </Link>
        </div>
      </main>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-4">
      <p className="font-serif text-2xl font-semibold tabular-nums">{value}</p>
      <p className="mt-1 text-sm text-ink-2">{label}</p>
      {sub && <p className="mt-0.5 text-xs text-ink-3">{sub}</p>}
    </div>
  );
}
