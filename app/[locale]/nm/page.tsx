import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { Header } from "@/components/ui/Header";
import { siteConfig } from "@/site.config";

export const revalidate = 3600;

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "area" });
  return { title: t("counties") };
}

export default async function AreasIndex({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "area" });
  return (
    <div className="min-h-dvh">
      <Header />
      <main className="mx-auto max-w-4xl px-5 py-10">
        <h1 className="font-serif text-3xl font-semibold tracking-tight">{t("counties")}</h1>
        <p className="mt-3 text-ink-2">{t("aggregateNote")}</p>
        <ul className="mt-8 grid gap-4 sm:grid-cols-2">
          {siteConfig.counties.map((c) => (
            <li key={c.slug} className="rounded-2xl border border-line bg-surface p-5">
              <Link href={`/nm/${c.slug}`} className="font-serif text-xl font-semibold hover:underline">
                {c.name} County
              </Link>
              <ul className="mt-3 space-y-1.5 text-sm">
                {c.cities.map((city) => (
                  <li key={city.slug}>
                    <Link href={`/nm/${c.slug}/${city.slug}`} className="text-accent hover:underline">{city.name}</Link>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
