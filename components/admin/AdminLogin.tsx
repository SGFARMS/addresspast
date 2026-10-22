"use client";

import { useState } from "react";

export function AdminLogin() {
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    const password = String(new FormData(e.currentTarget).get("password") ?? "");
    const r = await fetch("/api/admin/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ password }),
    }).catch(() => null);
    setBusy(false);
    if (r?.ok) location.reload();
    else setErr(r?.status === 429 ? "Too many tries. Wait a few minutes." : "That password didn't work.");
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center p-6">
      <h1 className="font-serif text-2xl font-semibold">AddressPast review</h1>
      <form onSubmit={submit} className="mt-6 space-y-3">
        <label className="block text-sm font-medium">
          Password
          <input
            name="password"
            type="password"
            required
            autoComplete="current-password"
            className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 focus:border-accent focus:outline-none"
          />
        </label>
        {err && <p role="alert" className="text-sm">{err}</p>}
        <button disabled={busy} className="w-full rounded-xl bg-accent px-4 py-2.5 font-semibold text-accent-ink disabled:opacity-60">
          {busy ? "Checking…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
