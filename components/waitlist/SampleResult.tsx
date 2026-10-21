import { useTranslations } from "next-intl";
import { Info } from "lucide-react";

/** Static illustration of the result screen. Fake data, labeled as such. */
export function SampleResult() {
  const t = useTranslations();
  const rows = [
    { year: "1932", cat: t("causes.homicide"), badge: t("precision.street"), approx: false, dist: null, color: "#6E5C80" },
    { year: "1961", cat: t("causes.accident"), badge: t("precision.street"), approx: false, dist: null, color: "#5E7A8F" },
    { year: "1897", cat: t("causes.homicide"), badge: t("precision.street"), approx: false, dist: "160 m", color: "#6E5C80" },
    { year: "1884", cat: t("causes.fire"), badge: t("precision.street_historic", { radius: 150 }), approx: true, dist: "240 m", color: "#B08A47" },
  ];
  return (
    <figure aria-label={t("waitlist.sampleLabel")} className="relative">
      <div className="absolute -inset-4 -z-10 rounded-[2rem] bg-gradient-to-br from-adobe-soft via-transparent to-accent-soft" aria-hidden />
      <div className="overflow-hidden rounded-3xl border border-line bg-surface shadow-card">
        <div className="relative h-36 overflow-hidden border-b border-line bg-surface-2" aria-hidden>
          <svg viewBox="0 0 400 144" className="h-full w-full" preserveAspectRatio="xMidYMid slice">
            <rect width="400" height="144" fill="var(--surface-2)" />
            {[20, 60, 100, 140].map((y) => <path key={y} d={`M0 ${y} H400`} stroke="var(--line)" strokeWidth="6" />)}
            {[40, 120, 200, 280, 360].map((x) => <path key={x} d={`M${x} 0 V144`} stroke="var(--line)" strokeWidth="6" />)}
            <circle cx="200" cy="74" r="58" fill="var(--accent)" opacity="0.07" stroke="var(--accent)" strokeDasharray="4 4" />
            <circle cx="162" cy="52" r="24" fill="#B08A47" opacity="0.14" stroke="#B08A47" strokeDasharray="3 3" />
            <circle cx="162" cy="52" r="6" fill="white" stroke="#B08A47" strokeWidth="2.5" />
            <circle cx="236" cy="96" r="7" fill="#6E5C80" stroke="white" strokeWidth="2" />
            <path d="M200 76s10-10.5 10-18.3A10 10 0 0 0 190 57.7c0 7.8 10 18.3 10 18.3Z" fill="var(--adobe)" stroke="white" strokeWidth="2" />
          </svg>
        </div>
        <div className="space-y-3 p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-3">{t("check.heading")}</p>
          <p className="font-serif text-lg font-semibold">
            {t("check.atAddress", { count: 2 })} · {t("check.nearby", { count: 2, radius: "250 m" })}
          </p>
          <ul className="divide-y divide-line rounded-2xl border border-line">
            {rows.map((r) => (
              <li key={r.year} className="flex items-center gap-3 px-3 py-2.5 text-sm">
                <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden>
                  <circle cx="8" cy="8" r="6" fill={r.approx ? "none" : r.color} stroke={r.color} strokeWidth="2" />
                </svg>
                <span className="font-semibold tabular-nums">{r.year}</span>
                <span className="text-ink-2">{r.cat}</span>
                <span className={`ml-auto flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] ${r.approx ? "bg-adobe-soft" : "bg-accent-soft"}`}>
                  {r.approx && <Info size={11} aria-hidden />}
                  {r.dist ?? r.badge}
                </span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-ink-3">{t("disclaimer")}</p>
        </div>
      </div>
      <figcaption className="mt-3 text-center text-xs text-ink-3">{t("waitlist.sampleLabel")}</figcaption>
    </figure>
  );
}
