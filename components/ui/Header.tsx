"use client";

import { useLocale, useTranslations } from "next-intl";
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, usePathname } from "@/i18n/navigation";
import { siteConfig } from "@/site.config";
import { Logo } from "./Logo";

export function useTheme() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const el = document.documentElement;
    setDark(el.classList.contains("dark"));
    const obs = new MutationObserver(() => setDark(el.classList.contains("dark")));
    obs.observe(el, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);
  const toggle = () => {
    const next = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("ap-theme", next ? "dark" : "light");
    } catch {}
  };
  return { dark, toggle };
}

export function Header({ compact = false }: { compact?: boolean }) {
  const t = useTranslations("nav");
  const locale = useLocale();
  const pathname = usePathname();
  const { dark, toggle } = useTheme();
  const other = locale === "en" ? "es" : "en";

  return (
    <header className={`flex items-center justify-between gap-3 px-4 ${compact ? "h-14" : "h-16"} border-b border-line bg-surface/95 backdrop-blur`}>
      <Link href="/" aria-label={t("home")} className="flex items-center gap-2 rounded-md">
        <Logo />
        <span className="font-serif text-lg font-semibold tracking-tight">{siteConfig.logoText}</span>
      </Link>
      <nav className="flex items-center gap-1 text-sm">
        <Link href="/nm" className="hidden rounded-md px-3 py-2 text-ink-2 hover:bg-surface-2 hover:text-ink sm:inline-block">
          {t("areas")}
        </Link>
        <Link
          href={pathname}
          locale={other}
          hrefLang={other}
          aria-label={t("languageLabel")}
          className="rounded-md px-3 py-2 font-medium text-ink-2 hover:bg-surface-2 hover:text-ink"
        >
          {t("language")}
        </Link>
        <button
          type="button"
          onClick={toggle}
          aria-label={dark ? t("themeLight") : t("themeDark")}
          className="rounded-md p-2 text-ink-2 hover:bg-surface-2 hover:text-ink"
        >
          {dark ? <Sun size={18} aria-hidden /> : <Moon size={18} aria-hidden />}
        </button>
      </nav>
    </header>
  );
}
