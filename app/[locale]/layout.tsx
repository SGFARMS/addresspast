import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import { Public_Sans, Source_Serif_4 } from "next/font/google";
import { NextIntlClientProvider, hasLocale } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Analytics } from "@vercel/analytics/next";
import { routing } from "@/i18n/routing";
import { siteConfig } from "@/site.config";

const body = Public_Sans({ subsets: ["latin"], variable: "--font-body", display: "swap" });
const display = Source_Serif_4({ subsets: ["latin"], variable: "--font-display", display: "swap" });

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "meta" });
  return {
    metadataBase: new URL(siteConfig.url),
    title: { default: t("title"), template: `%s · ${siteConfig.name}` },
    description: t("description"),
    applicationName: siteConfig.name,
    alternates: { canonical: locale === "en" ? "/" : `/${locale}`, languages: { en: "/", es: "/es" } },
    robots: siteConfig.launched ? { index: true, follow: true } : { index: false, follow: false, nocache: true },
    openGraph: { siteName: siteConfig.name, title: t("title"), description: t("description"), locale, type: "website" },
    twitter: { card: "summary_large_image" },
    manifest: "/manifest.webmanifest",
  };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f2ea" },
    { media: "(prefers-color-scheme: dark)", color: "#161412" },
  ],
};

// Applies the saved/system theme before paint so there's no flash.
const themeScript = `try{var t=localStorage.getItem('ap-theme');var d=t?t==='dark':matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.classList.toggle('dark',d)}catch(e){}`;

export default async function LocaleLayout({ children, params }: { children: ReactNode; params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);
  const meta = await getTranslations({ locale, namespace: "meta" });
  // Structured data for search engines (schema.org WebApplication).
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    name: siteConfig.name,
    url: siteConfig.url,
    description: meta("description"),
    applicationCategory: "ReferenceApplication",
    operatingSystem: "Web",
    inLanguage: locale,
    areaServed: { "@type": "State", name: siteConfig.state.name },
  };
  return (
    <html lang={locale} className={`${body.variable} ${display.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-dvh bg-bg text-ink">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
        <Analytics />
      </body>
    </html>
  );
}
