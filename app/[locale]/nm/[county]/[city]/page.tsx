import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { repo } from "@/lib/data";
import { getAreaSummary } from "@/lib/ai/area-summary";
import { AREA_VIEW, findCity } from "@/lib/areas";
import { routing } from "@/i18n/routing";
import { siteConfig } from "@/site.config";
import { AreaView } from "@/components/area/AreaView";

export const revalidate = 3600;

type P = { params: Promise<{ locale: string; county: string; city: string }> };

export function generateStaticParams() {
  return routing.locales.flatMap((locale) =>
    siteConfig.counties.flatMap((c) => c.cities.map((city) => ({ locale, county: c.slug, city: city.slug }))),
  );
}

export async function generateMetadata({ params }: P): Promise<Metadata> {
  const { locale, county, city } = await params;
  const found = findCity(county, city);
  if (!found) return {};
  const t = await getTranslations({ locale, namespace: "area" });
  return {
    title: t("title", { area: found.city.name }),
    description: t("description", { area: found.city.name }),
    alternates: { canonical: `${locale === "en" ? "" : "/es"}/nm/${county}/${city}` },
  };
}

export default async function CityPage({ params }: P) {
  const { locale, county, city } = await params;
  setRequestLocale(locale);
  const found = findCity(county, city);
  if (!found) notFound();
  const area = found.city.name;
  const stats = await repo().areaStats(found.county.name, found.city.name, false);
  const summary = await getAreaSummary({ county: found.county.name, city: found.city.name, area, stats, locale });
  return (
    <AreaView
      locale={locale}
      area={area}
      stats={stats}
      summary={summary}
      view={AREA_VIEW[found.city.slug]}
      breadcrumbs={[
        { href: "/nm", label: "New Mexico" },
        { href: `/nm/${found.county.slug}`, label: `${found.county.name} County` },
        { href: `/nm/${found.county.slug}/${found.city.slug}`, label: area },
      ]}
    />
  );
}
