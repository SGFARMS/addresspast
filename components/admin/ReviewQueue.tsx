"use client";

import { useCallback, useEffect, useState } from "react";
import { ExternalLink, LogOut, MapPin, RefreshCw } from "lucide-react";
import type { AdminAction, AdminQueue, ReviewDispute, ReviewIncident, ReviewSuggestion } from "@/lib/admin/types";

type Tab = "incidents" | "suggestions" | "disputes";

const TABS: { id: Tab; label: string; help: string }[] = [
  { id: "disputes", label: "Removal requests", help: "Fast-lane requests are already hidden. Remove keeps it hidden; restore puts it back." },
  { id: "incidents", label: "Held records", help: "Boarding houses, hotels and businesses stay off the site until you approve them." },
  { id: "suggestions", label: "Old addresses", help: "Claude's guess at where a pre-1960 address is today. Accept only when the reasoning holds up." },
];

export function ReviewQueue() {
  const [q, setQ] = useState<AdminQueue | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("disputes");
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    const r = await fetch("/api/admin/queue", { cache: "no-store" }).catch(() => null);
    if (r?.status === 401) return location.reload();
    if (!r?.ok) return setErr("Couldn't load the queue.");
    setQ(await r.json());
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(a: AdminAction) {
    const key = `${a.type}:${a.id}`;
    setBusy(key);
    const r = await fetch("/api/admin/action", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(a),
    }).catch(() => null);
    setBusy(null);
    if (!r?.ok) return setErr("That didn't save. Try again.");
    setQ((cur) => {
      if (!cur) return cur;
      if (a.type === "incident") return { ...cur, incidents: cur.incidents.filter((x) => x.id !== a.id) };
      if (a.type === "suggestion") return { ...cur, suggestions: cur.suggestions.filter((x) => x.id !== a.id) };
      return { ...cur, disputes: cur.disputes.filter((x) => x.id !== a.id) };
    });
  }

  async function logout() {
    await fetch("/api/admin/logout", { method: "POST" }).catch(() => null);
    location.reload();
  }

  const counts: Record<Tab, number> = {
    incidents: q?.incidents.length ?? 0,
    suggestions: q?.suggestions.length ?? 0,
    disputes: q?.disputes.length ?? 0,
  };

  return (
    <main className="mx-auto max-w-3xl p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-serif text-2xl font-semibold">Review queue</h1>
          {q && (
            <p className="mt-1 text-sm text-ink-2">
              {q.backend === "demo" ? "Demo data (database not connected) · " : ""}
              {q.stats.incidentsTotal.toLocaleString()} source records · {q.stats.eventsVisible.toLocaleString()} public ·
              harvest spend ${q.stats.harvestSpendUsd.toFixed(2)} of $20
              {q.stats.lastRun && ` · last job ${q.stats.lastRun.job} (${q.stats.lastRun.status})`}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => void load()} className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-sm hover:bg-surface-2">
            <RefreshCw size={15} aria-hidden /> Refresh
          </button>
          <button type="button" onClick={() => void logout()} className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-sm hover:bg-surface-2">
            <LogOut size={15} aria-hidden /> Sign out
          </button>
        </div>
      </header>

      <nav className="mt-5 flex flex-wrap gap-2" aria-label="Queues">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            aria-pressed={tab === t.id}
            className={`rounded-full border px-3.5 py-1.5 text-sm font-medium ${tab === t.id ? "border-accent bg-accent-soft" : "border-line hover:bg-surface-2"}`}
          >
            {t.label} <span className="tabular-nums text-ink-3">{counts[t.id]}</span>
          </button>
        ))}
      </nav>
      <p className="mt-3 text-sm text-ink-3">{TABS.find((t) => t.id === tab)!.help}</p>
      {err && <p role="alert" className="mt-3 rounded-lg bg-adobe-soft p-3 text-sm">{err}</p>}
      {!q && !err && <div className="skeleton mt-4 h-32" role="status"><span className="sr-only">Loading…</span></div>}

      {q && (
        <ul className="mt-4 space-y-3">
          {tab === "incidents" && q.incidents.map((i) => <IncidentCard key={i.id} i={i} busy={busy === `incident:${i.id}`} act={act} />)}
          {tab === "suggestions" && q.suggestions.map((s) => <SuggestionCard key={s.id} s={s} busy={busy === `suggestion:${s.id}`} act={act} />)}
          {tab === "disputes" && q.disputes.map((d) => <DisputeCard key={d.id} d={d} busy={busy === `dispute:${d.id}`} act={act} />)}
          {counts[tab] === 0 && <li className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-ink-2">Nothing waiting here.</li>}
        </ul>
      )}
    </main>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return <li className="rounded-2xl border border-line bg-surface p-4">{children}</li>;
}

function Btn({ children, onClick, busy, tone = "plain" }: { children: React.ReactNode; onClick: () => void; busy: boolean; tone?: "go" | "stop" | "plain" }) {
  const cls = tone === "go" ? "bg-accent text-accent-ink" : tone === "stop" ? "bg-adobe-soft text-ink border border-adobe/40" : "border border-line";
  return (
    <button type="button" disabled={busy} onClick={onClick} className={`rounded-lg px-3 py-1.5 text-sm font-semibold disabled:opacity-50 ${cls}`}>
      {children}
    </button>
  );
}

function Source({ url, name, date }: { url: string; name: string | null; date: string | null }) {
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm text-accent hover:underline">
      <ExternalLink size={14} aria-hidden /> {name ?? "Source"}{date ? `, ${date}` : ""}
    </a>
  );
}

function IncidentCard({ i, busy, act }: { i: ReviewIncident; busy: boolean; act: (a: AdminAction) => void }) {
  return (
    <Card>
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-3">{i.reviewReason ?? "Held"} · {i.cause}</p>
      {i.outsideArea && (
        <p className="mt-1 text-xs font-medium text-ink-2">
          Couldn&apos;t place this anywhere in New Mexico. Approving won&apos;t put it on the map; Hide is fine.
        </p>
      )}
      <p className="mt-1 font-medium">{i.addressRaw}{i.unit ? ` (${i.unit})` : ""}{i.city ? `, ${i.city}` : ""}</p>
      <p className="mt-1 text-sm text-ink-2">{i.summary}</p>
      <p className="mt-1 text-xs text-ink-3">
        Date {i.incidentDate ?? "unknown"} · confidence {i.confidence != null ? Math.round(i.confidence * 100) + "%" : "?"}
      </p>
      <div className="mt-2"><Source url={i.sourceUrl} name={i.sourceName} date={i.publishedDate} /></div>
      <div className="mt-3 flex gap-2">
        <Btn tone="go" busy={busy} onClick={() => act({ type: "incident", id: i.id, action: "approve" })}>Approve</Btn>
        <Btn tone="stop" busy={busy} onClick={() => act({ type: "incident", id: i.id, action: "hide" })}>Hide</Btn>
      </div>
    </Card>
  );
}

function SuggestionCard({ s, busy, act }: { s: ReviewSuggestion; busy: boolean; act: (a: AdminAction) => void }) {
  const map = `https://www.openstreetmap.org/?mlat=${s.suggestedLat}&mlon=${s.suggestedLng}#map=18/${s.suggestedLat}/${s.suggestedLng}`;
  return (
    <Card>
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-3">{s.year ?? "Year unknown"} · {s.city ?? ""}</p>
      <p className="mt-1 font-medium">Printed: {s.addressRaw}</p>
      <p className="mt-1 text-sm">
        Suggested: {s.suggestedAddress ?? `${s.suggestedLat.toFixed(5)}, ${s.suggestedLng.toFixed(5)}`}{" "}
        <a href={map} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-accent hover:underline">
          <MapPin size={14} aria-hidden /> map
        </a>
      </p>
      {s.rationale && <p className="mt-1 text-sm text-ink-2">{s.rationale}</p>}
      {s.summary && <p className="mt-1 text-xs text-ink-3">{s.summary}</p>}
      <div className="mt-2"><Source url={s.sourceUrl} name="Source page" date={null} /></div>
      <div className="mt-3 flex gap-2">
        <Btn tone="go" busy={busy} onClick={() => act({ type: "suggestion", id: s.id, action: "accept" })}>Accept location</Btn>
        <Btn busy={busy} onClick={() => act({ type: "suggestion", id: s.id, action: "reject" })}>Reject</Btn>
      </div>
    </Card>
  );
}

function DisputeCard({ d, busy, act }: { d: ReviewDispute; busy: boolean; act: (a: AdminAction) => void }) {
  return (
    <Card>
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-3">
        {d.fastLane ? "Fast lane · hidden already · " : ""}{d.relationship} · {d.reason.replace("_", " ")}
      </p>
      <p className="mt-1 font-medium">
        Record: {d.eventYear ?? "?"} {d.eventCause ?? ""}{d.eventCity ? `, ${d.eventCity}` : ""}
        {d.eventHidden != null && <span className="text-sm font-normal text-ink-3"> ({d.eventHidden ? "hidden" : "public"})</span>}
      </p>
      {d.details && <p className="mt-1 text-sm text-ink-2">“{d.details}”</p>}
      <p className="mt-1 text-xs text-ink-3">From {d.requesterEmail} · {new Date(d.createdAt).toLocaleString()}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Btn tone="stop" busy={busy} onClick={() => act({ type: "dispute", id: d.id, action: "remove" })}>Remove record</Btn>
        <Btn busy={busy} onClick={() => act({ type: "dispute", id: d.id, action: "corrected" })}>Fixed the details</Btn>
        <Btn busy={busy} onClick={() => act({ type: "dispute", id: d.id, action: "restore" })}>Keep it public</Btn>
      </div>
    </Card>
  );
}
