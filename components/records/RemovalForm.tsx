"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { track } from "@/lib/analytics";

const RELATIONSHIPS = ["family", "owner", "tenant", "agent", "other"] as const;
const REASONS = ["remove", "wrong_location", "wrong_details", "other"] as const;

type State = "closed" | "open" | "sending" | "done" | "doneFast" | "error";

export function RemovalForm({ eventId }: { eventId: string }) {
  const t = useTranslations("removal");
  const [state, setState] = useState<State>("closed");

  if (state === "closed") {
    return (
      <button
        type="button"
        onClick={() => setState("open")}
        className="w-fit rounded-lg border border-line px-3 py-2 text-sm text-ink-2 hover:bg-surface-2 hover:text-ink"
      >
        {t("open")}
      </button>
    );
  }

  if (state === "done" || state === "doneFast") {
    return (
      <p role="status" className="rounded-xl border border-accent/30 bg-accent-soft/60 p-3 text-sm">
        {t(state)}
      </p>
    );
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setState("sending");
    try {
      const r = await fetch("/api/removal", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          eventId,
          email: f.get("email"),
          relationship: f.get("relationship"),
          reason: f.get("reason"),
          details: f.get("details") || undefined,
          website: f.get("website") || undefined,
        }),
      });
      if (!r.ok) throw new Error(String(r.status));
      const j = await r.json();
      track("removal_request", { fastLane: Boolean(j.fastLane) });
      setState(j.fastLane ? "doneFast" : "done");
    } catch {
      setState("error");
    }
  }

  const field = "mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm focus:border-accent focus:outline-none";
  return (
    <form onSubmit={submit} aria-labelledby="removal-title" className="space-y-3 rounded-2xl border border-line bg-surface-2/50 p-4">
      <h3 id="removal-title" className="font-serif font-semibold">{t("title")}</h3>
      <p className="text-sm text-ink-2">{t("intro")}</p>
      <label className="block text-sm font-medium">
        {t("email")}
        <input name="email" type="email" required maxLength={200} autoComplete="email" className={field} />
      </label>
      <label className="block text-sm font-medium">
        {t("relationship")}
        <select name="relationship" required defaultValue="family" className={field}>
          {RELATIONSHIPS.map((r) => <option key={r} value={r}>{t(`relationships.${r}`)}</option>)}
        </select>
      </label>
      <label className="block text-sm font-medium">
        {t("reason")}
        <select name="reason" required defaultValue="remove" className={field}>
          {REASONS.map((r) => <option key={r} value={r}>{t(`reasons.${r}`)}</option>)}
        </select>
      </label>
      <label className="block text-sm font-medium">
        {t("details")}
        <textarea name="details" rows={3} maxLength={2000} className={field} />
      </label>
      <input name="website" tabIndex={-1} autoComplete="off" aria-hidden className="hidden" />
      {state === "error" && <p role="alert" className="text-sm text-ink">{t("error")}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={state === "sending"}
          className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-accent-ink hover:opacity-90 disabled:opacity-60"
        >
          {state === "sending" ? t("sending") : t("submit")}
        </button>
        <button type="button" onClick={() => setState("closed")} className="text-sm text-ink-2 hover:underline">
          {t("cancel")}
        </button>
      </div>
      <p className="text-xs text-ink-3">{t("privacy")}</p>
    </form>
  );
}
