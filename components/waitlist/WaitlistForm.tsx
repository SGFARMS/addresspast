"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { track } from "@/lib/analytics";

export function WaitlistForm({ counties }: { counties: { slug: string; name: string }[] }) {
  const t = useTranslations("waitlist");
  const locale = useLocale();
  const [state, setState] = useState<"idle" | "sending" | "ok" | "exists" | "error">("idle");

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setState("sending");
    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: fd.get("email"), county: fd.get("county") || null, locale, website: fd.get("website") || undefined }),
      });
      const json = await res.json();
      if (!res.ok) return setState("error");
      setState(json.status === "exists" ? "exists" : "ok");
      track("waitlist_join");
    } catch {
      setState("error");
    }
  }

  if (state === "ok" || state === "exists") {
    return (
      <p role="status" className="rounded-2xl border border-accent/30 bg-accent-soft p-4 font-medium">
        {t(state)}
      </p>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3" noValidate={false}>
      <div className="flex flex-col gap-2 sm:flex-row">
        <label className="sr-only" htmlFor="wl-email">{t("emailLabel")}</label>
        <input
          id="wl-email"
          name="email"
          type="email"
          required
          autoComplete="email"
          placeholder={t("emailPlaceholder")}
          className="min-w-0 flex-1 rounded-xl border border-line bg-surface px-4 py-3 text-base placeholder:text-ink-3 focus:border-accent focus:outline-none"
        />
        <button type="submit" disabled={state === "sending"} className="rounded-xl bg-accent px-5 py-3 font-semibold text-accent-ink hover:opacity-90 disabled:opacity-60">
          {state === "sending" ? t("sending") : t("submit")}
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor="wl-county" className="text-ink-2">{t("countyLabel")}</label>
        <select id="wl-county" name="county" className="rounded-lg border border-line bg-surface px-2 py-1.5">
          <option value="">{t("countyAny")}</option>
          {counties.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
        </select>
      </div>
      {/* Honeypot for bots */}
      <input type="text" name="website" tabIndex={-1} autoComplete="off" aria-hidden className="hidden" />
      {state === "error" && <p role="alert" className="text-sm text-adobe">{t("error")}</p>}
      <p className="text-xs text-ink-3">{t("privacy")}</p>
    </form>
  );
}
