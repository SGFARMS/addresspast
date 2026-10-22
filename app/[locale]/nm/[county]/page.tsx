import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { areaStatsForPage } from "@/lib/data";
import { getAreaSummary } from "@/lib/ai/area-summary";
import { AREA_VIEW, findCounty } from "@/lib/areas";
import { routing } from "@/i18n/routing";
import { siteConfig } from "@/site.config";
import { Link } from "@/i18n/navigation";
import { AreaView } from "@/components/area/AreaView";

export const revalidate = 3600;

type P = { params: Promise<{ locale: string; county: string }> };

export function generateStaticParams() {
  return routing.locales.flatMap((locale) => siteConfig.counties.map((c) => ({ locale, county: c.slug })));
}

export async function generateMetadata({ params }: P): Promise<Metadata> {
  const { locale, county } = await params;
  const c = findCounty(county);
  if (!c) return {};
  const t = await getTranslations({ locale, namespace: "area" });
  const area = `${c.name} County`;
  return {
    title: t("title", { area }),
    description: t("description", { area }),
    alternates: { canonical: `${locale === "en" ? "" : "/es"}/nm/${c.slug}` },
  };
}

export default async function CountyPage({ params }: P) {
  const { locale, county } = await params;
  setRequestLocale(locale);
  const c = findCounty(county);
  if (!c) notFound();
  const t = await getTranslations({ locale, namespace: "area" });
  const area = `${c.name} County`;
  const stats = await areaStatsForPage(c.name, null);
  const summary = await getAreaSummary({ county: c.name, city: null, area, stats, locale });
  return (
    <AreaView
      locale={locale}
      area={area}
      stats={stats}
      summary={summary}
      view={AREA_VIEW[c.slug]}
      breadcrumbs={[{ href: "/nm", label: "New Mexico" }, { href: `/nm/${c.slug}`, label: area }]}
    >
      <section className="mt-10">
        <h2 className="font-serif text-xl font-semibold">{t("cities")}</h2>
        <ul className="mt-3 flex flex-wrap gap-2">
          {c.cities.map((city) => (
            <li key={city.slug}>
              <Link href={`/nm/${c.slug}/${city.slug}`} className="inline-block rounded-full border border-line bg-surface px-4 py-2 text-sm hover:border-accent">
                {city.name}
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </AreaView>
  );
}
