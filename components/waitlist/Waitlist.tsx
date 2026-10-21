import { useTranslations } from "next-intl";
import { Check } from "lucide-react";
import { siteConfig } from "@/site.config";
import { Header } from "@/components/ui/Header";
import { WaitlistForm } from "./WaitlistForm";
import { SampleResult } from "./SampleResult";

/** Pre-launch home: short pitch, a sample result, and an email signup. */
export function Waitlist() {
  const t = useTranslations("waitlist");
  const f = useTranslations("footer");
  const points = ["free", "sources", "map", "spanish"] as const;
  return (
    <div className="flex min-h-dvh flex-col">
      <Header />
      <main className="mx-auto grid w-full max-w-6xl flex-1 items-center gap-10 px-5 py-10 md:grid-cols-[1.1fr_1fr] md:gap-14 md:py-16">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-adobe">{t("eyebrow")}</p>
          <h1 className="mt-3 font-serif text-4xl font-semibold leading-[1.1] tracking-tight md:text-5xl">{t("headline")}</h1>
          <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink-2">{t("body")}</p>
          <ul className="mt-6 space-y-2.5">
            {points.map((p) => (
              <li key={p} className="flex items-start gap-2.5">
                <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
                  <Check size={13} strokeWidth={3} aria-hidden />
                </span>
                <span>{t(`points.${p}`)}</span>
              </li>
            ))}
          </ul>
          <div className="mt-8 max-w-lg">
            <WaitlistForm counties={siteConfig.counties.map((c) => ({ slug: c.slug, name: c.name }))} />
          </div>
        </div>
        <div className="md:pl-4">
          <SampleResult />
        </div>
      </main>
      <footer className="border-t border-line px-5 py-6 text-center text-xs text-ink-3">
        <p>{f("pilot")}</p>
        <p className="mt-1">{f("rights")}</p>
      </footer>
    </div>
  );
}
